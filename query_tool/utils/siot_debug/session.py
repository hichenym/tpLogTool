from __future__ import annotations

import ctypes
import hashlib
import json
import logging
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.runtime_credential_cache import (
    invalidate_cached_cloud_credentials,
    load_cached_cloud_credentials,
    save_cached_cloud_credentials,
)

from .command_catalog import (
    get_command_keyword,
    is_getsystemcfg_command,
    is_startlogp2p_command,
    is_syscmd_family_command,
    parse_startlogp2p_level,
)
from .config import (
    CLOUD_ACCESS_URL,
    CLOUD_AUTH_BASIC,
    CLOUD_LOGIN_URL,
    DEFAULT_COMMAND_TIMEOUT_MS,
    DEFAULT_EMPTY_RESULT_SETTLE_S,
    DEFAULT_WAKEUP_INTERVAL_MS,
    DEFAULT_WAKEUP_RETRY_COUNT,
    SDK_BIN_DIR,
    FILE_INLINE_OUTPUT_MAX_BYTES,
    DEFAULT_QUERY_DEVICE_DELAY_S,
    DEFAULT_TEXT_RESULT_SETTLE_S,
    DEVICE_GATEWAY_ID,
    resolve_sdk_bin_dir,
)
from .models import CloudCredentials, CommandResult, DeviceCredentials, ParsedPayload, ProgressCallback, TransferProgress


def _safe_log_text(value) -> str:
    text = str(value or "")
    return text.encode("utf-8", errors="backslashreplace").decode("utf-8")
from .protocol import (
    PAYLOAD_TYPE_JSON,
    build_auth_xml,
    build_system_log_xml,
    decode_secret_key,
    extract_printable_text,
    make_text_output,
    pack_message,
    parse_device_payload,
    unpack_message,
)
from .siot_client import (
    SdkLibraries,
    SiotError,
    TPSIOT_DeviceMessage,
    TPSIOT_EventCallback,
    TPSRTC_PeerEventCallback,
    TPSRTC_RecvDataCallback,
    TPSRTC_SendSDPCallback,
)


TPSIOT_ROLE_APP = 2
TPSIOT_PROTOCOL_TCP = 2
TPSIOT_TERMINAL_NORMAL = 0

TPSIOT_CONN_CLOSED = 0
TPSIOT_CONN_FAILED = 2
TPSIOT_CONN_HANDSHAKED = 4
TPSIOT_CONN_HANDSHAKED_FAILED = 5
TPSIOT_CONN_APP_RECEIVED_DATA = 10
TPSIOT_CONN_RECONNECT_THRESHOLD = 12

TPSIOT_FB_QUERY_DEVICE = 0x1
TPSIOT_FB_UNREACHABLE_DEVICE = 0x2

TPSRTC_NET_MODE_AUTO = 0
TPSRTC_PEER_EVENT_DATA_CHANNEL_CONNECTED = 1
TPSRTC_PEER_EVENT_DATA_CHANNEL_TIMEOUT = 2
TPSRTC_PEER_EVENT_DATA_CHANNEL_CLOSED = 3
TPSRTC_PEER_DATATYPE_MSG = 0
TPSRTC_FILE_STREAM = 0

TPSIOT_PROPERTY_ACCESS_ADDR = 0
TPSIOT_PROPERTY_ACCESS_PROTOCOL = 1
TPSIOT_PROPERTY_CLIENT_ID = 2
TPSIOT_PROPERTY_TOKEN = 4
TPSIOT_PROPERTY_KEY_INDEX = 5

TPSRTC_PROPERTY_ENDPOINT = 0
TPSRTC_PROPERTY_LOGLEVEL = 1
TPSRTC_PROPERTY_ASSIGN_RELAY_SERVER = 4
TPSRTC_PROPERTY_RELAY_TOKEN = 6
TPSRTC_PROPERTY_RELAY_KEY_INDEX = 7
TPSRTC_PROPERTY_ICE_GATHER_TIMEOUT = 8
TPSRTC_PROPERTY_P2P_TIMEOUT = 10
TPSRTC_PROPERTY_P2P_KEEPALIVE = 11
TPSRTC_PROPERTY_AUTO_TRANSPORT = 36

ERR_P2P_USER_NOT_AUTH = 8
HEARTBEAT_INTERVAL_S = 10.0
FILE_IDLE_SETTLE_S = 0.35
MAX_CLOUD_CREDENTIAL_REFRESH_RETRIES = 2
INTERACTIVE_COMMAND_START_TIMEOUT_MS = 5_000


class CloudCredentialRefreshRequired(SiotError):
    def __init__(self, stage: str, reason: str, message: str, user_message: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.reason = reason
        self.user_message = user_message or message


def _build_heartbeat_xml() -> bytes:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<XML_TOPSEE>\n"
        '  <MESSAGE_HEADER Msg_type="TPS_HEARTBEAT_MESSAGE" Msg_code="CMD_HEARTBEAT" Msg_flag="0"/>\n'
        "  <MESSAGE_BODY></MESSAGE_BODY>\n"
        "</XML_TOPSEE>"
    )
    return xml.encode("utf-8")


def _describe_payload_error(payload: ParsedPayload) -> str:
    message_type = (payload.message_type or "").strip()
    msg_flag = (payload.msg_flag or "").strip()
    if not msg_flag or msg_flag == "0":
        return ""
    if msg_flag == str(ERR_P2P_USER_NOT_AUTH):
        return "设备认证已失效，请重新连接。"
    if message_type == "TPS_COMMON_MESSAGE" and msg_flag == "-100":
        return "设备交互会话已失效，已尝试自动重建。"
    if message_type:
        return f"{message_type} 返回错误，flag={msg_flag}"
    return f"设备返回错误，flag={msg_flag}"


def _http_post(url: str, data: str, headers: dict[str, str]) -> dict:
    body = data.encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, context=context, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers, method="GET")
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, context=context, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_cloud_credentials(username: str, password: str, force_refresh: bool = False) -> CloudCredentials:
    if not force_refresh:
        cached_credentials = load_cached_cloud_credentials(username, password)
        if cached_credentials is not None:
            logging.info("Using cached SIOT cloud credentials")
            return cached_credentials

    client_id = f"windows-siot-{uuid.uuid4().hex}"
    login_headers = {
        "Authorization": CLOUD_AUTH_BASIC,
        "Content-Type": "application/x-www-form-urlencoded",
        "Seetong-os": "and",
        "Seetong-Lang": "zh_CN",
        "Seetong-Phone-Brand": "windows",
        "Seetong-Phone-Type": "pc",
        "Seetong-App-Name": "seetong",
        "Seetong-App-Version": "1.4",
        "Seetong-Client-Id": client_id,
    }

    login_body = urllib.parse.urlencode(
        {
            "grant_type": "seetong_password",
            "username": username,
            "password": hashlib.md5(password.encode("utf-8")).hexdigest(),
        }
    )

    logging.info("Logging in to cloud platform...")
    login_response = _http_post(CLOUD_LOGIN_URL, login_body, login_headers)
    if login_response.get("code") != 200:
        raise SiotError(f"cloud login failed: {login_response.get('msg', login_response)}")

    access_token = login_response["access_token"]
    access_headers = {
        "Seetong-Auth": f"bearer {access_token}",
        "Seetong-os": "and",
        "Seetong-Lang": "zh_CN",
        "Seetong-Phone-Brand": "windows",
        "Seetong-Phone-Type": "pc",
        "Seetong-App-Name": "seetong",
        "Seetong-App-Version": "1.4",
        "Seetong-Client-Id": client_id,
    }

    logging.info("Fetching SIOT access credentials...")
    access_response = _http_get(CLOUD_ACCESS_URL, access_headers)
    if access_response.get("code") != 200:
        raise SiotError(f"cloud access-node fetch failed: {access_response.get('msg', access_response)}")

    data = access_response["data"]
    relay_nodes = ",".join(f"{item['relayNode']}:{item['netType']}" for item in data.get("relayNodes", []))
    vip_relay_nodes = ",".join(f"{item['relayNode']}:{item['netType']}" for item in data.get("vipRelayNodes", []))
    credentials = CloudCredentials(
        client_id=client_id,
        access_node=data.get("accessNode", ""),
        access_jwt_token=data.get("accessJwtToken", ""),
        relay_jwt_token=data.get("relayJwtToken", ""),
        relay_nodes=relay_nodes,
        vip_relay_nodes=vip_relay_nodes,
        jwt_key_version=int(data.get("signKeyVer", 0)),
    )
    save_cached_cloud_credentials(username, password, credentials)
    logging.info("SIOT credentials obtained successfully")
    logging.info("  Access node: %s", credentials.access_node)
    return credentials


@dataclass
class _CommandWaiter:
    command: str
    command_kind: str
    expects_file: bool = False
    progress_callback: Optional[ProgressCallback] = None
    responses: list[ParsedPayload] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)
    binary_chunks: bytearray = field(default_factory=bytearray)
    filename: Optional[str] = None
    file_started: bool = False
    file_finished: bool = False
    has_error: bool = False
    packet_count: int = 0
    received_bytes: int = 0
    last_activity: float = field(default_factory=time.monotonic)
    last_progress: float = field(default_factory=time.monotonic)
    event: threading.Event = field(default_factory=threading.Event)

    def feed(self, payload: ParsedPayload) -> None:
        self.responses.append(payload)
        now = time.monotonic()
        self.last_activity = now

        if payload.filename:
            self.filename = payload.filename

        if payload.message_type == "SYSTEM_LOG_DATA" or payload.data_len > 0:
            if not self.expects_file:
                self.event.set()
                return
            self.file_started = True
            self.packet_count += 1
            if payload.data_len > 0 and payload.binary_payload:
                self._append_chunk(payload.start_pos, payload.binary_payload[: payload.data_len])
                self.received_bytes = max(self.received_bytes, payload.start_pos + payload.data_len)
                self.last_progress = now
            else:
                self.file_finished = True
            self._notify_progress(payload)
            self.event.set()
            return

        text = extract_printable_text(payload).strip()
        if text:
            if not self.text_parts or self.text_parts[-1] != text:
                self.text_parts.append(text)
            if payload.msg_flag and payload.msg_flag != "0":
                self.has_error = True
            self.event.set()
            return

        if payload.msg_flag and payload.msg_flag != "0":
            self.has_error = True
            self.event.set()
            return

        self.event.set()

    def _append_chunk(self, start_pos: int, chunk: bytes) -> None:
        offset = max(start_pos, 0)
        required = offset + len(chunk)
        if len(self.binary_chunks) < required:
            self.binary_chunks.extend(b"\x00" * (required - len(self.binary_chunks)))
        self.binary_chunks[offset:required] = chunk

    def has_text(self) -> bool:
        return bool(self.text_parts)

    def has_ack_only(self) -> bool:
        return bool(self.responses) and not self.text_parts and not self.binary_chunks and not self.has_error

    def build_result(self) -> CommandResult:
        if self.text_parts:
            text = "\n".join(self.text_parts)
            return CommandResult(
                command=self.command,
                command_kind=self.command_kind,
                success=not self.has_error,
                display_text=text,
                acknowledged=True,
                received_bytes=self.received_bytes,
                streamed_packets=self.packet_count,
                responses=self.responses,
            )

        if self.binary_chunks:
            binary = bytes(self.binary_chunks)
            suppress_content = self.expects_file and len(binary) > FILE_INLINE_OUTPUT_MAX_BYTES
            text = "" if suppress_content else make_text_output(binary)
            return CommandResult(
                command=self.command,
                command_kind=self.command_kind,
                success=not self.has_error,
                display_text=text,
                acknowledged=True,
                binary_payload=binary,
                filename=self.filename,
                received_bytes=max(self.received_bytes, len(binary)),
                streamed_packets=self.packet_count,
                content_suppressed=suppress_content,
                responses=self.responses,
            )

        if self.has_error:
            return CommandResult(
                command=self.command,
                command_kind=self.command_kind,
                success=False,
                display_text=self._build_error_text(),
                acknowledged=bool(self.responses),
                filename=self.filename,
                received_bytes=self.received_bytes,
                streamed_packets=self.packet_count,
                responses=self.responses,
            )

        return CommandResult(
            command=self.command,
            command_kind=self.command_kind,
            success=bool(self.responses) and not self.has_error,
            display_text="",
            acknowledged=bool(self.responses),
            filename=self.filename,
            received_bytes=self.received_bytes,
            streamed_packets=self.packet_count,
            responses=self.responses,
        )

    def _build_error_text(self) -> str:
        for payload in reversed(self.responses):
            text = extract_printable_text(payload).strip()
            if text:
                return text
            fallback = _describe_payload_error(payload)
            if fallback:
                return fallback
        return "命令执行失败。"

    def _notify_progress(self, payload: ParsedPayload) -> None:
        if self.progress_callback is None:
            return
        try:
            self.progress_callback(
                TransferProgress(
                    command=self.command,
                    filename=self.filename or payload.filename or "",
                    start_pos=max(payload.start_pos, 0),
                    chunk_size=max(payload.data_len, 0),
                    received_bytes=self.received_bytes,
                    packet_index=self.packet_count,
                    finished=self.file_finished,
                )
            )
        except Exception:
            logging.exception("Progress callback failed for %s", self.command)


class DeviceSession:
    def __init__(
        self,
        cloud_username: str,
        cloud_password: str,
        prefetched_cloud_credentials: Optional[CloudCredentials] = None,
    ) -> None:
        self.sdk = SdkLibraries()
        self.lib = self.sdk.lib
        self.crypt = self.sdk.crypt
        self.device: Optional[DeviceCredentials] = None
        self.cloud_credentials: Optional[CloudCredentials] = None
        self.cloud_username = cloud_username
        self.cloud_password = cloud_password
        self._prefetched_cloud_credentials = prefetched_cloud_credentials

        self._siot_conn = None
        self._peer_conn = None

        self._signal_ready = threading.Event()
        self._status_ready = threading.Event()
        self._auth_ready = threading.Event()
        self._peer_ready = threading.Event()
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()

        self._signal_connected = False
        self._device_online = False
        self._device_is_4g = False
        self._authenticated = False
        self._peer_connected = False
        self._session_id = ""
        self._encrypt_method = 0
        self._secret_key = b""
        self._gateway_id = DEVICE_GATEWAY_ID
        self._gateway_id_4g = ""
        self._cloud_protocol = -1
        self._cloud_net_type = -1

        self._active_waiter: Optional[_CommandWaiter] = None
        self._waiter_lock = threading.Lock()
        self._stream_log_listener: Optional[Callable[[str], None]] = None
        self._stream_log_enabled = False
        self._interactive_command_ready = False
        self._interactive_command_keyword = ""

        self._heartbeat_thread: Optional[threading.Thread] = None
        self._status_callback: Optional[Callable[[str], None]] = None

        self._cb_siot_event = TPSIOT_EventCallback(self._on_siot_event)
        self._cb_peer_event = TPSRTC_PeerEventCallback(self._on_peer_event)
        self._cb_recv_data = TPSRTC_RecvDataCallback(self._on_peer_data)
        self._cb_send_sdp = TPSRTC_SendSDPCallback(self._on_send_sdp)

    def _load_cloud_credentials_for_connect(self, force_refresh: bool) -> CloudCredentials:
        if not force_refresh and self._prefetched_cloud_credentials is not None:
            credentials = self._prefetched_cloud_credentials
            self._prefetched_cloud_credentials = None
            logging.info("Using prefetched SIOT cloud credentials")
            return credentials
        return fetch_cloud_credentials(
            self.cloud_username,
            self.cloud_password,
            force_refresh=force_refresh,
        )

    def _query_device_wait_timeout(self) -> float:
        if self._current_gateway_id != DEVICE_GATEWAY_ID or self._device_online:
            return 0.0
        return DEFAULT_QUERY_DEVICE_DELAY_S

    def connect(self, device: DeviceCredentials, status_callback: Optional[Callable[[str], None]] = None) -> None:
        self.device = device
        self._status_callback = status_callback
        for retry_index in range(MAX_CLOUD_CREDENTIAL_REFRESH_RETRIES + 1):
            force_refresh = retry_index > 0
            try:
                self._connect_once(force_refresh=force_refresh)
                return
            except CloudCredentialRefreshRequired as exc:
                self.close()
                self.device = device
                self._status_callback = status_callback
                invalidate_cached_cloud_credentials(self.cloud_username, self.cloud_password)
                if retry_index >= MAX_CLOUD_CREDENTIAL_REFRESH_RETRIES:
                    raise SiotError(exc.user_message)
                logging.warning(
                    "Cloud credentials refresh retry %s/%s, stage=%s reason=%s message=%s",
                    retry_index + 1,
                    MAX_CLOUD_CREDENTIAL_REFRESH_RETRIES,
                    exc.stage,
                    exc.reason,
                    str(exc),
                )
                self._emit_status(
                    f"云凭证已刷新，正在进行第{retry_index + 1}次重试..."
                )
            except Exception:
                raise

    def _connect_once(self, force_refresh: bool) -> None:
        if self.device is None:
            raise SiotError("device credentials are missing")

        self._gateway_id = DEVICE_GATEWAY_ID
        self._gateway_id_4g = ""
        self._cloud_protocol = -1
        self._cloud_net_type = -1
        self._device_online = False
        self._device_is_4g = False
        self._emit_status("正在检查设备状态...")
        self.cloud_credentials = self._load_cloud_credentials_for_connect(force_refresh)
        status = self._probe_device_status_via_siot_helper(self.cloud_credentials)
        self._apply_device_status(status)
        if self._is_device_offline(status):
            self._emit_status(f"设备：{self.device.sn}不在线")
            raise SiotError(f"设备：{self.device.sn}不在线")
        if self._is_device_sleeping(status):
            self._emit_status("设备休眠，正在唤醒...")
            self._prepare_device_via_siot_helper()
            self._emit_status("唤醒成功，正在连接设备...")
        else:
            self._emit_status("设备已在线，正在连接设备...")
        self._emit_status("正在连接设备...")
        self._connect_signaling()
        self._query_device(wait_timeout=self._query_device_wait_timeout())
        self._authenticate_via_signaling()
        self._connect_peer()
        self._invalidate_interactive_command_session()
        self._start_heartbeat_loop()

    def _raise_cloud_refresh_required(
        self,
        stage: str,
        reason: str,
        message: str,
        user_message: str,
    ) -> None:
        raise CloudCredentialRefreshRequired(
            stage=stage,
            reason=reason,
            message=message,
            user_message=user_message,
        )

    def execute_command(
        self,
        command: str,
        timeout_ms: int = DEFAULT_COMMAND_TIMEOUT_MS,
        progress_callback: Optional[ProgressCallback] = None,
        stream_log_callback: Optional[Callable[[str], None]] = None,
    ) -> CommandResult:
        command = command.strip()
        if not command:
            raise SiotError("empty command")
        if not (is_syscmd_family_command(command) or is_getsystemcfg_command(command) or is_startlogp2p_command(command)):
            return CommandResult(command=command, command_kind="ignored", success=False, display_text="")

        self._ensure_ready()
        if self._should_prepare_interactive_command(command):
            self._ensure_interactive_command_session(command)

        result = self._execute_p2p_command(command, timeout_ms, progress_callback, stream_log_callback)
        self._update_interactive_command_state(command, result)

        if self._should_retry_with_interactive_restart(command, result):
            logging.info("Interactive command session appears stale, retrying command after restart: %s", _safe_log_text(command))
            self._invalidate_interactive_command_session()
            self._ensure_ready()
            self._ensure_interactive_command_session(command)
            result = self._execute_p2p_command(command, timeout_ms, progress_callback, stream_log_callback)
            self._update_interactive_command_state(command, result)

        return result

    def _ensure_ready(self) -> None:
        if self.device is None or self.cloud_credentials is None:
            raise SiotError("device session is not initialized")
        if not self._signal_connected:
            self._connect_signaling()
        if not self._authenticated:
            self._authenticate_via_signaling()
        if not self._peer_connected:
            self._connect_peer()

    @staticmethod
    def _is_interactive_start_command(command: str) -> bool:
        parts = command.strip().split(None, 1)
        if len(parts) != 2:
            return False
        keyword = parts[0]
        action = parts[1].strip().lower()
        return keyword in ("syscmd", "syscmdEx") and action == "start"

    def _should_prepare_interactive_command(self, command: str) -> bool:
        return is_syscmd_family_command(command) and not self._is_interactive_start_command(command)

    def _ensure_interactive_command_session(self, command: str) -> None:
        keyword = get_command_keyword(command)
        if keyword not in ("syscmd", "syscmdEx"):
            return
        if self._interactive_command_ready and self._interactive_command_keyword == keyword:
            return

        start_command = f"{keyword} start"
        logging.info("Initializing interactive command session via P2P: %s", start_command)
        init_result = self._execute_p2p_command(
            start_command,
            INTERACTIVE_COMMAND_START_TIMEOUT_MS,
            progress_callback=None,
            stream_log_callback=None,
        )
        self._update_interactive_command_state(start_command, init_result)
        if self._is_interactive_start_success(init_result):
            return

        message = (init_result.display_text or "").strip() or "初始化交互终端失败"
        raise SiotError(message)

    def _update_interactive_command_state(self, command: str, result: CommandResult) -> None:
        keyword = get_command_keyword(command)
        if keyword not in ("syscmd", "syscmdEx"):
            return
        if not self._is_interactive_start_command(command):
            if self._looks_like_interactive_session_lost(result):
                self._invalidate_interactive_command_session()
            return

        if self._is_interactive_start_success(result):
            self._interactive_command_keyword = keyword
            self._interactive_command_ready = True
        else:
            self._invalidate_interactive_command_session()

    def _should_retry_with_interactive_restart(self, command: str, result: CommandResult) -> bool:
        return self._should_prepare_interactive_command(command) and self._looks_like_interactive_session_lost(result)

    @staticmethod
    def _is_interactive_start_success(result: CommandResult) -> bool:
        return result.success or (
            not result.success
            and not result.acknowledged
            and not result.display_text
            and not result.responses
            and result.streamed_packets == 0
            and not result.binary_payload
        )

    @staticmethod
    def _looks_like_interactive_session_lost(result: CommandResult) -> bool:
        if result.success:
            return False
        if any(
            payload.message_type == "TPS_COMMON_MESSAGE" and payload.msg_flag == "-100"
            for payload in result.responses
        ):
            return True
        return not result.acknowledged and not (result.display_text or "").strip() and not result.responses

    def _invalidate_interactive_command_session(self) -> None:
        self._interactive_command_ready = False
        self._interactive_command_keyword = ""

    def _connect_signaling(self) -> None:
        if self.cloud_credentials is None:
            raise SiotError("cloud credentials are missing")

        with self._state_lock:
            if self._siot_conn and self._signal_connected:
                return
            if self._siot_conn and not self._signal_connected:
                try:
                    self.lib.TPSIOT_Close(self._siot_conn)
                finally:
                    self._siot_conn = None
            if self._peer_conn and not self._peer_connected:
                try:
                    self.lib.TPSRTC_DisconnectPeer(self._peer_conn)
                finally:
                    self._peer_conn = None
            self.lib.TPSRTC_Cleanup()

            self._signal_ready.clear()
            self._configure_rtc_properties(self.cloud_credentials)
            ret = self.lib.TPSRTC_Startup(None, None, None, 0, 0)
            if ret != 0:
                raise SiotError(f"TPSRTC_Startup failed: {ret}")

            self._configure_tpsiot_properties(self.cloud_credentials)
            logging.info("Connecting to signaling server: %s", self.cloud_credentials.access_node)
            self._siot_conn = self.lib.TPSIOT_Connect(
                TPSIOT_ROLE_APP,
                TPSIOT_PROTOCOL_TCP,
                TPSIOT_TERMINAL_NORMAL,
                self._cb_siot_event,
                None,
            )
            if not self._siot_conn:
                self.lib.TPSRTC_Cleanup()
                self._raise_cloud_refresh_required(
                    "signaling",
                    "connect_null",
                    "TPSIOT_Connect returned NULL",
                    "连接信令服务失败",
                )

        if not self._signal_ready.wait(15.0) or not self._signal_connected:
            self.close()
            self._raise_cloud_refresh_required(
                "signaling",
                "connect_timeout",
                "failed to connect signaling server",
                "连接信令服务失败",
            )

        ret = self.lib.TPSRTC_Init(None, self._cb_send_sdp, None, None, None)
        if ret != 0:
            self.close()
            raise SiotError(f"TPSRTC_Init failed: {ret}")

    def _configure_rtc_properties(self, credentials: CloudCredentials) -> None:
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_ENDPOINT, credentials.client_id.encode("utf-8"))
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_LOGLEVEL, b"off")
        if credentials.relay_jwt_token:
            self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_RELAY_TOKEN, credentials.relay_jwt_token.encode("utf-8"))
            self.lib.TPSRTC_SetProperties(
                TPSRTC_PROPERTY_RELAY_KEY_INDEX,
                str(credentials.jwt_key_version).encode("utf-8"),
            )
        if credentials.relay_nodes:
            self.lib.TPSRTC_SetProperties(
                TPSRTC_PROPERTY_ASSIGN_RELAY_SERVER,
                credentials.relay_nodes.encode("utf-8"),
            )
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_ICE_GATHER_TIMEOUT, b"1000")
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_P2P_TIMEOUT, b"3000")
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_P2P_KEEPALIVE, b"5000")
        self.lib.TPSRTC_SetProperties(TPSRTC_PROPERTY_AUTO_TRANSPORT, b"2")

    def _configure_tpsiot_properties(self, credentials: CloudCredentials) -> None:
        self.lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_ACCESS_ADDR, credentials.access_node.encode("utf-8"))
        self.lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_ACCESS_PROTOCOL, b"2")
        self.lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_CLIENT_ID, credentials.client_id.encode("utf-8"))
        self.lib.TPSIOT_SetProperties(TPSIOT_PROPERTY_TOKEN, credentials.access_jwt_token.encode("utf-8"))
        self.lib.TPSIOT_SetProperties(
            TPSIOT_PROPERTY_KEY_INDEX,
            str(credentials.jwt_key_version).encode("utf-8"),
        )

    def _query_device(self, wait_timeout: float = DEFAULT_QUERY_DEVICE_DELAY_S) -> None:
        if not self._siot_conn or self.device is None:
            raise SiotError("signaling connection is not ready")
        self._status_ready.clear()
        logging.info("Querying device status for %s", self.device.sn)
        ret = self.lib.TPSIOT_AppSend(
            self._siot_conn,
            TPSIOT_PROTOCOL_TCP,
            self.device.sn.encode("utf-8"),
            DEVICE_GATEWAY_ID.encode("utf-8"),
            None,
            0,
            b"query_dev",
            0,
            TPSIOT_FB_QUERY_DEVICE,
        )
        if ret != 0:
            logging.warning("TPSIOT_AppSend(query_dev) failed: %s", ret)
        if wait_timeout > 0:
            self._status_ready.wait(wait_timeout)

    def _authenticate_via_signaling(self) -> None:
        if not self._siot_conn or self.device is None:
            raise SiotError("signaling connection is not ready")

        self._auth_ready.clear()
        auth_xml = build_auth_xml(self.device.password, self.device.sn, self.device.username, self.crypt)
        packed = pack_message(
            auth_xml,
            payload_type=0x01,
            encrypt=False,
            method=0,
            key=b"",
            crypt_lib=self.crypt,
        )
        buffer = ctypes.create_string_buffer(packed, len(packed))
        logging.info("Authenticating device %s via signaling", self.device.sn)
        ret = self.lib.TPSIOT_AppSend(
            self._siot_conn,
            TPSIOT_PROTOCOL_TCP,
            self.device.sn.encode("utf-8"),
            self._current_gateway_id.encode("utf-8"),
            ctypes.cast(buffer, ctypes.c_void_p),
            len(packed),
            b"",
            0,
            0,
        )
        if ret != 0:
            raise SiotError(f"failed to send auth message: {ret}")

        if not self._auth_ready.wait(10.0) or not self._authenticated:
            raise SiotError("device authentication failed")

    def _connect_peer(self) -> None:
        if self.cloud_credentials is None or self.device is None:
            raise SiotError("session is not initialized")

        with self._state_lock:
            if self._peer_conn:
                self.lib.TPSRTC_DisconnectPeer(self._peer_conn)
                self._peer_conn = None
            self._peer_ready.clear()
            logging.info("Connecting P2P data channel for %s", self.device.sn)
            self._peer_conn = self.lib.TPSRTC_ConnectPeer(
                TPSRTC_NET_MODE_AUTO,
                self._cloud_net_type if self._cloud_net_type > 0 else 1,
                self.device.sn.encode("utf-8"),
                self._current_gateway_id.encode("utf-8"),
                self._cb_peer_event,
                self._cb_recv_data,
                self.cloud_credentials.vip_relay_nodes.encode("utf-8")
                if self.cloud_credentials.vip_relay_nodes
                else None,
                self.cloud_credentials.relay_jwt_token.encode("utf-8"),
                self.cloud_credentials.jwt_key_version,
                None,
                None,
                0,
                True,
                False,
            )
            if not self._peer_conn:
                self._raise_cloud_refresh_required(
                    "p2p",
                    "connect_null",
                    "TPSRTC_ConnectPeer returned NULL",
                    "建立P2P通道失败",
                )

        if not self._peer_ready.wait(20.0) or not self._peer_connected:
            self._raise_cloud_refresh_required(
                "p2p",
                "connect_timeout",
                "failed to establish P2P data channel",
                "建立P2P通道失败",
            )

    def _execute_p2p_command(
        self,
        command: str,
        timeout_ms: int,
        progress_callback: Optional[ProgressCallback],
        stream_log_callback: Optional[Callable[[str], None]],
    ) -> CommandResult:
        if not self._peer_conn:
            raise SiotError("peer connection is not ready")

        xml = build_system_log_xml(command)
        packed = pack_message(
            xml,
            payload_type=0x01,
            encrypt=self._encrypt_method > 0 and bool(self._secret_key),
            method=self._encrypt_method,
            key=self._secret_key,
            crypt_lib=self.crypt,
        )
        send_buffer = ctypes.create_string_buffer(packed, len(packed))
        is_file_command = is_getsystemcfg_command(command)
        waiter = _CommandWaiter(
            command=command,
            command_kind="system_log",
            expects_file=is_file_command,
            progress_callback=progress_callback,
        )
        log_level = parse_startlogp2p_level(command)
        enable_stream_log = is_startlogp2p_command(command) and log_level is not None and log_level != 0
        disable_stream_log = is_startlogp2p_command(command) and log_level == 0

        with self._waiter_lock:
            self._active_waiter = waiter

        try:
            logging.info("Executing device command via P2P: %s", _safe_log_text(command))
            ret = self.lib.TPSRTC_SendData(
                self._peer_conn,
                ctypes.cast(send_buffer, ctypes.c_void_p),
                len(packed),
                TPSRTC_FILE_STREAM,
                b"",
            )
            if ret != 0:
                raise SiotError(f"TPSRTC_SendData failed: {ret}")

            deadline = time.monotonic() + timeout_ms / 1000.0
            lowered = command.lower()

            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                waiter.event.wait(timeout=min(0.5, max(remaining, 0.0)))
                waiter.event.clear()

                if waiter.has_text():
                    settle_deadline = time.monotonic() + DEFAULT_TEXT_RESULT_SETTLE_S
                    while time.monotonic() < settle_deadline:
                        settle_remaining = settle_deadline - time.monotonic()
                        waiter.event.wait(timeout=min(0.1, max(settle_remaining, 0.0)))
                        waiter.event.clear()
                    result = waiter.build_result()
                    if enable_stream_log:
                        self._stream_log_listener = stream_log_callback
                        self._stream_log_enabled = True
                        result.keep_listening = True
                    elif disable_stream_log:
                        self._stream_log_listener = None
                        self._stream_log_enabled = False
                    return result

                if is_file_command and waiter.file_finished:
                    result = waiter.build_result()
                    if enable_stream_log:
                        self._stream_log_listener = stream_log_callback
                        self._stream_log_enabled = True
                        result.keep_listening = True
                    elif disable_stream_log:
                        self._stream_log_listener = None
                        self._stream_log_enabled = False
                    return result

                if is_file_command and waiter.file_started:
                    if time.monotonic() - waiter.last_progress >= FILE_IDLE_SETTLE_S:
                        result = waiter.build_result()
                        if enable_stream_log:
                            self._stream_log_listener = stream_log_callback
                            self._stream_log_enabled = True
                            result.keep_listening = True
                        elif disable_stream_log:
                            self._stream_log_listener = None
                            self._stream_log_enabled = False
                        return result

                if not is_file_command and waiter.has_ack_only():
                    settle_s = DEFAULT_EMPTY_RESULT_SETTLE_S
                    if lowered == "syscmd start":
                        settle_s = DEFAULT_TEXT_RESULT_SETTLE_S
                    if time.monotonic() - waiter.last_activity >= settle_s:
                        return waiter.build_result()

                if lowered == "syscmd start" and waiter.responses:
                    result = waiter.build_result()
                    if enable_stream_log:
                        self._stream_log_listener = stream_log_callback
                        self._stream_log_enabled = True
                        result.keep_listening = True
                    elif disable_stream_log:
                        self._stream_log_listener = None
                        self._stream_log_enabled = False
                    return result

            result = waiter.build_result()
            if enable_stream_log:
                self._stream_log_listener = stream_log_callback
                self._stream_log_enabled = True
                result.keep_listening = True
            elif disable_stream_log:
                self._stream_log_listener = None
                self._stream_log_enabled = False
            return result
        finally:
            with self._waiter_lock:
                if self._active_waiter is waiter:
                    self._active_waiter = None

    def _handle_transport_packet(self, raw: bytes, source: str) -> None:
        payload_type = self._get_payload_type(raw)
        unpacked = unpack_message(
            raw,
            method=self._encrypt_method,
            key=self._secret_key,
            crypt_lib=self.crypt,
        )
        if unpacked is None:
            unpacked = raw

        if payload_type == PAYLOAD_TYPE_JSON:
            self._handle_json_payload(unpacked)
            return

        if self._looks_like_json(unpacked):
            self._handle_device_status_payload(unpacked)
            return

        if not self._looks_like_xml(unpacked):
            return

        parsed = parse_device_payload(unpacked)
        logging.info(
            "Received %s payload type=%s flag=%s source=%s",
            parsed.message_type,
            parsed.msg_code,
            parsed.msg_flag,
            source,
        )
        self._handle_xml_payload(parsed)

    def _handle_json_payload(self, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8"))
        except Exception:
            logging.debug("Ignoring invalid signaling JSON payload")
            return

        if not isinstance(message, dict):
            return

        if {"online", "online4g", "devGatewayId", "devGatewayId4g"} & message.keys():
            self._apply_device_status(message)
            return

        payload_type = int(message.get("type", 0))
        if payload_type not in (2, 3) or "value" not in message or not self._siot_conn:
            return

        body = json.dumps(message["value"]).encode("utf-8")
        if payload_type == 2:
            self.lib.TPSRTC_ParseAnswer(self._siot_conn, body, len(body))
        else:
            self.lib.TPSRTC_ParseCandidates(self._siot_conn, body, len(body))

    def _handle_device_status_payload(self, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8"))
        except Exception:
            return
        if isinstance(message, dict):
            self._apply_device_status(message)

    def _apply_device_status(self, message: dict) -> None:
        online = int(message.get("online", 0) or 0)
        online4g = int(message.get("online4g", 0) or 0)
        protocol = message.get("protocol")
        net_type = message.get("netType")
        dev_gateway_id = message.get("devGatewayId") or ""
        dev_gateway_id_4g = message.get("devGatewayId4g") or ""

        self._device_online = online != 0
        self._device_is_4g = self._device_is_4g or online4g != 0 or bool(dev_gateway_id_4g)
        if isinstance(protocol, int):
            self._cloud_protocol = protocol
        if isinstance(net_type, int):
            self._cloud_net_type = net_type
        if dev_gateway_id:
            self._gateway_id = dev_gateway_id
        if dev_gateway_id_4g:
            self._gateway_id_4g = dev_gateway_id_4g
        elif dev_gateway_id and not self._gateway_id_4g:
            self._gateway_id_4g = dev_gateway_id

        logging.info(
            "Device status: online=%s online4g=%s gateway=%s gateway4g=%s protocol=%s netType=%s",
            online,
            online4g,
            self._gateway_id,
            self._gateway_id_4g,
            self._cloud_protocol,
            self._cloud_net_type,
        )
        self._status_ready.set()

    def _handle_xml_payload(self, parsed: ParsedPayload) -> None:
        if parsed.message_type == "TPS_COMMON_MESSAGE":
            if parsed.msg_flag == str(ERR_P2P_USER_NOT_AUTH):
                logging.warning("Device reported auth expired")
                self._authenticated = False
                self._invalidate_interactive_command_session()
            with self._waiter_lock:
                waiter = self._active_waiter
            if waiter is not None:
                waiter.feed(parsed)
            return

        if parsed.message_type == "IOT_CAMERA_MESSAGE":
            return

        if parsed.message_type == "USER_AUTH_MESSAGE":
            self._handle_auth_response(parsed)
            return

        if parsed.message_type in ("SYSTEM_LOG_MESSAGE", "SYSTEM_LOG_DATA", "SYSTEM_CONTROL_MESSAGE"):
            with self._waiter_lock:
                waiter = self._active_waiter
            if waiter is not None:
                waiter.feed(parsed)
                return
            self._handle_stream_log_payload(parsed)

    def _handle_stream_log_payload(self, parsed: ParsedPayload) -> None:
        if not self._stream_log_enabled:
            return
        if parsed.message_type != "SYSTEM_LOG_MESSAGE":
            return
        text = extract_printable_text(parsed).strip()
        if not text:
            return
        listener = self._stream_log_listener
        if listener is None:
            return
        try:
            listener(text)
        except Exception:
            logging.exception("Stream log callback failed")

    def _handle_auth_response(self, parsed: ParsedPayload) -> None:
        if parsed.msg_flag and parsed.msg_flag != "0":
            logging.error("Authentication failed with flag=%s", parsed.msg_flag)
            self._authenticated = False
            self._auth_ready.set()
            return

        session_id = self._extract_attr(parsed.xml_text, "USER_AUTH_RESPONSE", "Sessionid")
        rand_key = self._extract_attr(parsed.xml_text, "USER_AUTH_RESPONSE", "RandKey")
        encrypt_version_text = self._extract_attr(parsed.xml_text, "ENCRYPT", "Version")
        remote_version = int(encrypt_version_text) if encrypt_version_text.isdigit() else 0

        self._session_id = session_id
        if hasattr(self.crypt, "TpsProtocolEncryptVersionNegotiate"):
            self._encrypt_method = self.crypt.TpsProtocolEncryptVersionNegotiate(remote_version)
        else:
            self._encrypt_method = remote_version
        self._secret_key = decode_secret_key(rand_key, self.device.sn, self.crypt) if rand_key and self.device else b""
        if not self._secret_key and rand_key:
            self._secret_key = rand_key.encode("latin-1", errors="ignore")
        self._authenticated = True
        logging.info(
            "Authentication successful, session_id=%s encrypt_method=%s",
            self._session_id,
            self._encrypt_method,
        )
        self._auth_ready.set()

    def _start_heartbeat_loop(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="siot-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(HEARTBEAT_INTERVAL_S):
            try:
                if not self._signal_connected or not self._authenticated or not self._peer_connected:
                    self._ensure_ready()
                self._send_heartbeat()
            except Exception as exc:  # pragma: no cover
                logging.warning("Heartbeat failed: %s", exc)

    def _send_heartbeat(self) -> None:
        if not self._siot_conn or not self._authenticated or self.device is None:
            return
        heartbeat_xml = _build_heartbeat_xml()
        packed = pack_message(
            heartbeat_xml,
            payload_type=0x01,
            encrypt=False,
            method=0,
            key=b"",
            crypt_lib=self.crypt,
        )
        buffer = ctypes.create_string_buffer(packed, len(packed))
        ret = self.lib.TPSIOT_AppSend(
            self._siot_conn,
            TPSIOT_PROTOCOL_TCP,
            self.device.sn.encode("utf-8"),
            self._current_gateway_id.encode("utf-8"),
            ctypes.cast(buffer, ctypes.c_void_p),
            len(packed),
            b"",
            0,
            0,
        )
        if ret == 0:
            logging.info("Heartbeat sent")
        else:
            logging.warning("TPSIOT_AppSend(heartbeat) failed: %s", ret)

    def _on_siot_event(self, conn, event, err_code, data_ptr, data_len, arg) -> None:
        if event == TPSIOT_CONN_HANDSHAKED:
            self._signal_connected = True
            self._signal_ready.set()
            logging.info("Signaling handshake successful")
            return

        if event in (TPSIOT_CONN_HANDSHAKED_FAILED, TPSIOT_CONN_FAILED, TPSIOT_CONN_CLOSED):
            self._signal_connected = False
            self._authenticated = False
            self._peer_connected = False
            self._invalidate_interactive_command_session()
            self._signal_ready.set()
            logging.warning("Signaling event failed/closed: event=%s err=%s", event, err_code)
            return

        if event == TPSIOT_CONN_RECONNECT_THRESHOLD and self.cloud_credentials and self._siot_conn:
            logging.warning("Signaling reconnect threshold reached, refreshing access point")
            self._refresh_redirect_access()
            return

        if event != TPSIOT_CONN_APP_RECEIVED_DATA or not data_ptr:
            return

        message = ctypes.cast(data_ptr, ctypes.POINTER(TPSIOT_DeviceMessage)).contents
        if message.feedbackCode == TPSIOT_FB_UNREACHABLE_DEVICE:
            self._device_online = False
            if self._peer_connected:
                self._log_unreachable_signaling(keep_session=True)
                self._status_ready.set()
                return
            self._authenticated = False
            self._peer_connected = False
            self._log_unreachable_signaling(keep_session=False)
            self._status_ready.set()
            self._auth_ready.set()
            return
        if not message.buffer or message.len == 0:
            return
        raw = ctypes.string_at(message.buffer, message.len)
        if message.feedbackCode == TPSIOT_FB_QUERY_DEVICE:
            self._handle_device_status_payload(raw)
            return
        self._handle_transport_packet(raw, source="signaling")

    def _on_peer_event(self, conn, event, err_code, data_ptr, data_len, arg) -> None:
        if event == TPSRTC_PEER_EVENT_DATA_CHANNEL_CONNECTED:
            self._peer_connected = True
            self._peer_ready.set()
            logging.info("P2P data channel connected")
            return

        if event in (TPSRTC_PEER_EVENT_DATA_CHANNEL_TIMEOUT, TPSRTC_PEER_EVENT_DATA_CHANNEL_CLOSED):
            self._peer_connected = False
            self._invalidate_interactive_command_session()
            self._peer_ready.set()
            logging.warning("P2P data channel closed or timeout: event=%s err=%s", event, err_code)
            return

    def _on_peer_data(self, conn, stream_id, data_type, data_ptr, data_len, arg) -> None:
        if data_type != TPSRTC_PEER_DATATYPE_MSG or not data_ptr or data_len == 0:
            return
        raw = ctypes.string_at(data_ptr, data_len)
        self._handle_transport_packet(raw, source="p2p")

    def _on_send_sdp(self, sdp_type, sdp_ptr, sdp_len, peer_id, usr_routing, arg) -> None:
        if not self._siot_conn or not sdp_ptr or sdp_len == 0 or self.device is None:
            return
        sdp_text = ctypes.string_at(sdp_ptr, sdp_len)
        try:
            sdp_json = json.loads(sdp_text.decode("utf-8"))
        except Exception:
            return

        body = json.dumps({"type": int(sdp_type), "value": sdp_json}).encode("utf-8")
        packet = (
            (0x51589158).to_bytes(4, "little")
            + len(body).to_bytes(4, "little")
            + bytes([PAYLOAD_TYPE_JSON, 0, 0, 0])
            + body
        )
        buffer = ctypes.create_string_buffer(packet, len(packet))
        target_peer = peer_id.decode("utf-8") if peer_id else self.device.sn
        target_route = usr_routing.decode("utf-8") if usr_routing else self._current_gateway_id
        self.lib.TPSIOT_AppSend(
            self._siot_conn,
            TPSIOT_PROTOCOL_TCP,
            target_peer.encode("utf-8"),
            target_route.encode("utf-8"),
            ctypes.cast(buffer, ctypes.c_void_p),
            len(packet),
            b"",
            0,
            0,
        )

    @staticmethod
    def _get_payload_type(raw: bytes) -> int:
        if len(raw) < 9:
            return 0
        lead_code = int.from_bytes(raw[:4], "little")
        if lead_code not in (0x51589158, 0x52598157):
            return 0
        return raw[8]

    @staticmethod
    def _looks_like_xml(raw: bytes) -> bool:
        stripped = raw.lstrip()
        return stripped.startswith(b"<?xml") or b"<XML_TOPSEE>" in raw

    @staticmethod
    def _extract_attr(xml: str, element: str, attr: str) -> str:
        marker = f"<{element}"
        start = xml.find(marker)
        if start < 0:
            return ""
        end = xml.find(">", start)
        if end < 0:
            return ""
        segment = xml[start:end + 1]
        key = f'{attr}="'
        pos = segment.find(key)
        if pos < 0:
            return ""
        value_start = pos + len(key)
        value_end = segment.find('"', value_start)
        return segment[value_start:value_end] if value_end >= 0 else ""

    def close(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        self._heartbeat_thread = None

        with self._waiter_lock:
            self._active_waiter = None

        if self._peer_conn:
            try:
                self.lib.TPSRTC_DisconnectPeer(self._peer_conn)
            finally:
                self._peer_conn = None

        if self._siot_conn:
            try:
                self.lib.TPSIOT_Close(self._siot_conn)
            finally:
                self._siot_conn = None

        self.lib.TPSRTC_Cleanup()
        self._signal_connected = False
        self._authenticated = False
        self._peer_connected = False
        self._invalidate_interactive_command_session()
        self._session_id = ""
        self._encrypt_method = 0
        self._secret_key = b""
        self._gateway_id = DEVICE_GATEWAY_ID
        self._gateway_id_4g = ""
        self._cloud_protocol = -1
        self._cloud_net_type = -1
        self._device_online = False
        self._device_is_4g = False
        self._status_callback = None
        self._stream_log_listener = None
        self._stream_log_enabled = False

    def __enter__(self) -> "DeviceSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def _current_gateway_id(self) -> str:
        if self._device_is_4g and self._gateway_id_4g:
            return self._gateway_id_4g
        return self._gateway_id or DEVICE_GATEWAY_ID

    def _prepare_device_via_siot_helper(self) -> None:
        if self.device is None:
            raise SiotError("device session is not initialized")

        logging.info("Preparing device via libsiot helper: %s", self.device.sn)
        params = {
            "cloud_username": self.cloud_username,
            "cloud_password": self.cloud_password,
            "gateway_id": "",
            "is_4g": True,
            "status_timeout_ms": 10_000,
            "login_timeout_ms": 30_000,
            "command_timeout_ms": DEFAULT_COMMAND_TIMEOUT_MS,
            "wakeup_interval_ms": DEFAULT_WAKEUP_INTERVAL_MS,
            "wakeup_retry_count": DEFAULT_WAKEUP_RETRY_COUNT,
            "debug": False,
        }
        proc = subprocess.Popen(
            build_internal_command(
                "--siot-helper-prepare",
                str(resolve_sdk_bin_dir(SDK_BIN_DIR)),
                json.dumps(params, separators=(",", ":")),
                self.device.sn,
                self.device.username,
                self.device.password,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        saw_wakeup = False
        helper_lines: list[str] = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                text = line.rstrip()
                if not text:
                    continue
                helper_lines.append(text)
                if "Waking up 4G device" in text and not saw_wakeup:
                    saw_wakeup = True
                    self._emit_status("设备休眠，正在唤醒...")
                logging.info("Wakeup helper: %s", text)
            proc.wait(timeout=90)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise SiotError("wakeup helper timed out")

        helper_output = "\n".join(helper_lines)
        if proc.returncode != 0:
            helper_error = helper_output.strip() or f"exit code {proc.returncode}"
            raise SiotError(f"wakeup helper failed: {helper_error}")
        logging.info("libsiot prepare/login helper succeeded for %s", self.device.sn)

    def _probe_device_status_via_siot_helper(self, credentials: CloudCredentials) -> dict:
        if self.device is None:
            raise SiotError("device session is not initialized")

        logging.info("Probing device status via signaling helper: %s", self.device.sn)
        probe_params = {
            "access_node": credentials.access_node,
            "access_token": credentials.access_jwt_token,
            "client_id": credentials.client_id,
            "key_version": credentials.jwt_key_version,
            "sn": self.device.sn,
        }
        proc = subprocess.run(
            build_internal_command(
                "--siot-helper-probe",
                str(resolve_sdk_bin_dir(SDK_BIN_DIR)),
                json.dumps(probe_params, separators=(",", ":")),
            ),
            capture_output=True,
            text=True,
            timeout=40,
        )
        combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
        if combined:
            logging.info("Probe helper output:\n%s", combined)
        if proc.returncode != 0:
            raise SiotError(combined or "device status probe failed")

        for line in reversed(proc.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                if "probe_error" in payload:
                    raise SiotError(str(payload["probe_error"]))
                return payload
        raise SiotError("device status probe returned no valid payload")

    @staticmethod
    def _is_device_sleeping(status: dict) -> bool:
        return int(status.get("online", 0) or 0) == 0 and int(status.get("online4g", 0) or 0) != 0

    @staticmethod
    def _is_device_offline(status: dict) -> bool:
        return int(status.get("online", 0) or 0) == 0 and int(status.get("online4g", 0) or 0) == 0

    def _emit_status(self, message: str) -> None:
        if self._status_callback is None:
            return
        try:
            self._status_callback(message)
        except Exception:
            logging.exception("Status callback failed: %s", message)

    def _refresh_redirect_access(self) -> None:
        if not self._siot_conn:
            return
        try:
            self.cloud_credentials = fetch_cloud_credentials(
                self.cloud_username,
                self.cloud_password,
                force_refresh=True,
            )
            ret = self.lib.TPSIOT_RedirectAccess(
                self._siot_conn,
                self.cloud_credentials.access_node.encode("utf-8"),
                self.cloud_credentials.access_jwt_token.encode("utf-8"),
                self.cloud_credentials.jwt_key_version,
            )
            if ret != 0:
                logging.warning("TPSIOT_RedirectAccess failed after refresh: %s", ret)
        except Exception as exc:
            logging.warning("Refresh redirect access failed: %s", exc)

    def _log_unreachable_signaling(self, keep_session: bool) -> None:
        if keep_session:
            return
        logging.warning("Device is unreachable via signaling")

    @staticmethod
    def _looks_like_json(raw: bytes) -> bool:
        stripped = raw.lstrip()
        return stripped.startswith(b"{") or stripped.startswith(b"[")
