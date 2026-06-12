from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .command_catalog import (
    get_command_keyword,
    is_getsystemcfg_command,
    is_startlogp2p_command,
    is_syscmd_family_command,
    parse_startlogp2p_level,
)
from .config import (
    DEFAULT_EMPTY_RESULT_SETTLE_S,
    DEFAULT_TEXT_RESULT_SETTLE_S,
    PROJECT_ROOT,
    SDK_BIN_DIR,
)
from .models import CommandResult, DeviceCredentials, ParsedPayload, ProgressCallback
from .protocol import decode_text, extract_printable_text, parse_device_payload
from .session import INTERACTIVE_COMMAND_START_TIMEOUT_MS, _CommandWaiter, _safe_log_text
from .siot_client import SiotError


P2P_CONNECT_TIMEOUT_S = 30.0
REMOTE_DIAGNOSE_COMMAND = 1
REMOTE_DIAGNOSE_CHANNEL = -1

TPS_MSG_BASE = 0x2000
TPS_MSG_NOTIFY_LOGIN_OK = TPS_MSG_BASE + 1
TPS_MSG_NOTIFY_LOGIN_FAILED = TPS_MSG_BASE + 2
TPS_MSG_P2P_CONNECT_OK = TPS_MSG_BASE + 10
TPS_MSG_P2P_OFFLINE = TPS_MSG_BASE + 13
TPS_MSG_NOTIFY_AUTH_FAILED = TPS_MSG_BASE + 23
TPS_MSG_NOTIFY_P2P_TCP_TIMEOUT = TPS_MSG_BASE + 28
TPS_P2P_NOTIFY_SVR_LOGIN_OK = TPS_MSG_BASE + 31
TPS_MSG_NOTIFY_P2P_THREAD_EXIT = TPS_MSG_BASE + 34
TPS_MSG_P2P_LOG = TPS_MSG_BASE + 46
TPS_MSG_NOTIFY_LOGIN_AGAIN = TPS_MSG_BASE + 48

P2P_DEVICE_USERNAME = "admin"
P2P_LOGIN_DEVICE_LIST_PARSE_WARNING = -2105006

P2P_FAILURE_EVENTS = {
    TPS_MSG_P2P_OFFLINE,
    TPS_MSG_NOTIFY_AUTH_FAILED,
    TPS_MSG_NOTIFY_P2P_TCP_TIMEOUT,
    TPS_MSG_NOTIFY_P2P_THREAD_EXIT,
    TPS_MSG_NOTIFY_LOGIN_AGAIN,
}

MsgRspCallback = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_uint,
)

FcLogCallback = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_char_p)


def _read_callback_payload(data_ptr, data_len: int) -> bytes:
    if not data_ptr or data_len <= 0:
        return b""
    try:
        return ctypes.string_at(data_ptr, data_len)
    except Exception:
        return b""


def _decode_p2p_error_code(raw: bytes) -> Optional[int]:
    if len(raw) != 4:
        return None
    return int.from_bytes(raw, byteorder="little", signed=True)


def _extract_p2p_payload_text(raw: bytes) -> str:
    if not raw or len(raw) == 4:
        return ""
    try:
        text = decode_text(raw).replace("\x00", "").strip()
    except Exception:
        return ""
    if not text:
        return ""
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
    if printable / max(len(text), 1) < 0.80:
        return ""
    return text


def _looks_like_device_id_text(text: str) -> bool:
    text = (text or "").strip()
    return text.isdigit() and 6 <= len(text) <= 16


def _is_generic_disconnect_message(text: str) -> bool:
    text = (text or "").strip()
    if not text:
        return True
    if _looks_like_device_id_text(text):
        return True
    return text.startswith("P2P会话线程已退出") or text.startswith("P2P连接异常(")


def _is_benign_p2p_login_return_code(code: int) -> bool:
    return int(code) == P2P_LOGIN_DEVICE_LIST_PARSE_WARNING


def _is_p2p_sdk_dir(path: Path) -> bool:
    path = Path(path)
    return path.is_dir() and (path / "Funclib.dll").exists()


def _iter_p2p_sdk_candidates():
    seen = set()

    def add(path_like):
        if not path_like:
            return
        try:
            path = Path(path_like).resolve()
        except Exception:
            return
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        yield path

    env_path = (os.environ.get("TPQUERYTOOL_P2P_SDK_DIR") or "").strip()
    if env_path:
        yield from add(env_path)

    yield from add(PROJECT_ROOT / "query_tool" / "dll")

    current_file = Path(__file__).resolve()
    if len(current_file.parents) >= 4:
        yield from add(current_file.parents[3] / "query_tool" / "dll")

    for base in filter(None, (sys.executable, sys.argv[0] if sys.argv else "")):
        base_dir = Path(base).resolve().parent
        yield from add(base_dir / "query_tool" / "dll")
        yield from add(base_dir / "dll")

    for parent in current_file.parents:
        yield from add(parent / "query_tool" / "dll")
        yield from add(parent / "dll")


def _iter_p2p_search_roots():
    seen = set()
    current_file = Path(__file__).resolve()
    roots = []

    if len(current_file.parents) >= 4:
        roots.append(current_file.parents[3])

    for base in filter(None, (sys.executable, sys.argv[0] if sys.argv else "")):
        roots.append(Path(base).resolve().parent)

    for root in roots:
        try:
            resolved = Path(root).resolve()
        except Exception:
            resolved = Path(root)
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        yield resolved


def resolve_p2p_sdk_dir(preferred: str | Path | None = None) -> Path:
    candidates = []
    if preferred:
        candidates.append(Path(preferred))
    candidates.extend(_iter_p2p_sdk_candidates())

    seen = set()
    for candidate in candidates:
        try:
            path = Path(candidate).resolve()
        except Exception:
            path = Path(candidate)
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if _is_p2p_sdk_dir(path):
            return path

    for root in _iter_p2p_search_roots():
        root_depth = len(root.parts)
        for current_root, dirnames, filenames in os.walk(root):
            current_path = Path(current_root)
            if len(current_path.parts) - root_depth > 4:
                dirnames[:] = []
                continue
            lowered_names = {name.lower() for name in filenames}
            if "funclib.dll" in lowered_names:
                return current_path

    if preferred:
        return Path(preferred)
    return PROJECT_ROOT / "query_tool" / "dll"


class _P2PCommandWaiter(_CommandWaiter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport_error = ""

    def build_result(self) -> CommandResult:
        if self.transport_error and not self.responses and not self.text_parts and not self.binary_chunks:
            return CommandResult(
                command=self.command,
                command_kind=self.command_kind,
                success=False,
                display_text=self.transport_error,
                acknowledged=False,
                filename=self.filename,
                received_bytes=self.received_bytes,
                streamed_packets=self.packet_count,
                responses=self.responses,
            )
        return super().build_result()


class P2PLibraries:
    _init_lock = threading.Lock()
    _initialized = False

    def __init__(self, sdk_bin_dir: Path | None = None) -> None:
        self.sdk_bin_dir = resolve_p2p_sdk_dir(sdk_bin_dir)
        self._runtime_dirs = self._resolve_runtime_dirs()
        self._dll_dir_handles = []
        self._configure_search_path()
        self._preload_runtime_libraries()
        self.lib = self._load_library("Funclib.dll")
        self._bind_low_level()

    def _resolve_runtime_dirs(self) -> list[Path]:
        runtime_dirs = []
        seen = set()
        for candidate in (self.sdk_bin_dir, Path(SDK_BIN_DIR), PROJECT_ROOT / "query_tool" / "dll"):
            try:
                path = Path(candidate).resolve()
            except Exception:
                path = Path(candidate)
            key = str(path).lower()
            if key in seen or not path.exists():
                continue
            seen.add(key)
            runtime_dirs.append(path)
        return runtime_dirs

    def _configure_search_path(self) -> None:
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            for runtime_dir in self._runtime_dirs:
                self._dll_dir_handles.append(os.add_dll_directory(str(runtime_dir)))

    def _preload_runtime_libraries(self) -> None:
        for name in ("libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll"):
            self._load_optional_runtime_library(name)

    def _load_optional_runtime_library(self, name: str) -> None:
        for runtime_dir in self._runtime_dirs:
            path = runtime_dir / name
            if not path.exists():
                continue
            try:
                self._load(path)
                return
            except OSError as exc:
                logging.debug("Optional runtime library load failed: %s (%s)", path, exc)

    def _load_library(self, name: str):
        path = self.sdk_bin_dir / name
        if not path.exists():
            raise FileNotFoundError(f"P2P SDK library not found: {path}")
        return self._load(path)

    @staticmethod
    def _load(path: Path):
        if sys.platform == "win32":
            return ctypes.CDLL(str(path))
        return ctypes.CDLL(str(path))

    def _bind_low_level(self) -> None:
        self.lib.FC_init.restype = ctypes.c_int
        self.lib.FC_init.argtypes = []

        self.lib.FC_SetMsgRspCallBack.restype = ctypes.c_int
        self.lib.FC_SetMsgRspCallBack.argtypes = [MsgRspCallback]

        self.lib.FC_SetfcLogCallBack.restype = ctypes.c_int
        self.lib.FC_SetfcLogCallBack.argtypes = [FcLogCallback]

        self.lib.FC_Login.restype = ctypes.c_int
        self.lib.FC_Login.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_ushort,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]

        self.lib.FC_Logout.restype = ctypes.c_int
        self.lib.FC_Logout.argtypes = []

        self.lib.FC_RemoteDiagnose.restype = ctypes.c_int
        self.lib.FC_RemoteDiagnose.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
        ]

    def configure_callbacks(self, message_callback: MsgRspCallback, log_callback: FcLogCallback) -> None:
        rc = self.lib.FC_SetMsgRspCallBack(message_callback)
        if rc != 0:
            raise SiotError(f"FC_SetMsgRspCallBack failed: {rc}")
        rc = self.lib.FC_SetfcLogCallBack(log_callback)
        if rc != 0:
            logging.warning("FC_SetfcLogCallBack failed: %s", rc)

    def ensure_initialized(self) -> None:
        cls = type(self)
        with cls._init_lock:
            if cls._initialized:
                return
            rc = self.lib.FC_init()
            if rc != 0:
                raise SiotError(f"FC_init failed: {rc}")
            cls._initialized = True


class P2PDeviceSession:
    def __init__(self) -> None:
        self.sdk = P2PLibraries()
        self.lib = self.sdk.lib
        self.device: Optional[DeviceCredentials] = None

        self._state_lock = threading.RLock()
        self._waiter_lock = threading.Lock()
        self._connect_ready = threading.Event()

        self._connected = False
        self._target_id = ""
        self._connect_error = ""
        self._disconnect_reason = ""

        self._active_waiter: Optional[_P2PCommandWaiter] = None
        self._stream_log_listener: Optional[Callable[[str], None]] = None
        self._stream_log_enabled = False
        self._interactive_command_ready = False
        self._interactive_command_keyword = ""
        self._status_callback: Optional[Callable[[str], None]] = None

        self._cb_message = MsgRspCallback(self._on_message)
        self._cb_log = FcLogCallback(self._on_log)
        self.sdk.configure_callbacks(self._cb_message, self._cb_log)
        self.sdk.ensure_initialized()

    def connect(self, device: DeviceCredentials, status_callback: Optional[Callable[[str], None]] = None) -> None:
        target_id = str(device.dev_id or device.sn or "").strip()
        if not target_id:
            raise SiotError("P2P设备缺少可用的设备标识")

        self.device = device
        self._status_callback = status_callback

        with self._state_lock:
            if self._connected and self._target_id == target_id:
                return
            self._target_id = target_id
            self._connect_error = ""
            self._disconnect_reason = ""
            self._connected = False
            self._connect_ready.clear()
            self._invalidate_interactive_command_session()

        self._logout_quietly()

        rc = self.lib.FC_Login(
            P2P_DEVICE_USERNAME.encode("utf-8"),
            (device.password or "").encode("utf-8"),
            target_id.encode("utf-8"),
            80,
            b"",
            b"",
            b"",
        )
        if rc != 0 and not _is_benign_p2p_login_return_code(rc):
            raise SiotError(f"P2P登录失败: {rc}")
        if rc != 0:
            logging.warning(
                "P2P FC_Login returned warning code %s for device %s; continuing to wait for callbacks",
                rc,
                target_id,
            )

        if not self._connect_ready.wait(P2P_CONNECT_TIMEOUT_S) or not self._connected:
            self._logout_quietly()
            timeout_message = self._connect_error or self._disconnect_reason
            if not timeout_message and rc != 0:
                timeout_message = f"P2P连接设备超时，登录返回码: {rc}"
            raise SiotError(timeout_message or "P2P连接设备超时")

    def execute_command(
        self,
        command: str,
        timeout_ms: int,
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
            logging.info("P2P interactive command session appears stale, retrying: %s", _safe_log_text(command))
            self._invalidate_interactive_command_session()
            self._ensure_ready()
            self._ensure_interactive_command_session(command)
            result = self._execute_p2p_command(command, timeout_ms, progress_callback, stream_log_callback)
            self._update_interactive_command_state(command, result)

        return result

    def _ensure_ready(self) -> None:
        if self.device is None:
            raise SiotError("device session is not initialized")
        if not self._connected:
            self.connect(self.device, self._status_callback)

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
        logging.info("Initializing P2P interactive command session: %s", start_command)
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
        return not result.acknowledged and not (result.display_text or "").strip() and not result.responses

    def _invalidate_interactive_command_session(self) -> None:
        self._interactive_command_ready = False
        self._interactive_command_keyword = ""

    def _execute_p2p_command(
        self,
        command: str,
        timeout_ms: int,
        progress_callback: Optional[ProgressCallback],
        stream_log_callback: Optional[Callable[[str], None]],
    ) -> CommandResult:
        if not self._target_id:
            raise SiotError("p2p session is not ready")

        payload = f"<cmd>{command}</cmd>".encode("gb2312", errors="ignore")
        is_file_command = is_getsystemcfg_command(command)
        waiter = _P2PCommandWaiter(
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
            logging.info("Executing device command via P2P Funclib: %s", _safe_log_text(command))
            ret = self.lib.FC_RemoteDiagnose(
                self._target_id.encode("utf-8"),
                REMOTE_DIAGNOSE_COMMAND,
                payload,
                REMOTE_DIAGNOSE_CHANNEL,
            )
            if ret != 0:
                raise SiotError(f"FC_RemoteDiagnose failed: {ret}")

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
                    self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                    return result

                if is_file_command and waiter.file_finished:
                    result = waiter.build_result()
                    self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                    return result

                if is_file_command and waiter.file_started:
                    if time.monotonic() - waiter.last_progress >= 0.35:
                        result = waiter.build_result()
                        self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                        return result

                if waiter.transport_error and not waiter.responses:
                    result = waiter.build_result()
                    self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                    return result

                if not is_file_command and waiter.has_ack_only():
                    settle_s = DEFAULT_EMPTY_RESULT_SETTLE_S
                    if lowered == "syscmd start":
                        settle_s = DEFAULT_TEXT_RESULT_SETTLE_S
                    if time.monotonic() - waiter.last_activity >= settle_s:
                        result = waiter.build_result()
                        self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                        return result

                if lowered == "syscmd start" and waiter.responses:
                    result = waiter.build_result()
                    self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
                    return result

            result = waiter.build_result()
            self._apply_stream_log_state(result, enable_stream_log, disable_stream_log, stream_log_callback)
            return result
        finally:
            with self._waiter_lock:
                if self._active_waiter is waiter:
                    self._active_waiter = None

    def _apply_stream_log_state(
        self,
        result: CommandResult,
        enable_stream_log: bool,
        disable_stream_log: bool,
        stream_log_callback: Optional[Callable[[str], None]],
    ) -> None:
        if enable_stream_log:
            self._stream_log_listener = stream_log_callback
            self._stream_log_enabled = True
            result.keep_listening = True
        elif disable_stream_log:
            self._stream_log_listener = None
            self._stream_log_enabled = False

    def _handle_transport_payload(self, raw: bytes) -> None:
        parsed = parse_device_payload(raw)
        if parsed.message_type:
            logging.info(
                "Received P2P payload type=%s code=%s flag=%s",
                parsed.message_type,
                parsed.msg_code,
                parsed.msg_flag,
            )
            self._handle_parsed_payload(parsed)
            return

        text = decode_text(raw).replace("\x00", "").strip()
        if not text:
            return

        fallback = ParsedPayload(
            message_type="SYSTEM_LOG_MESSAGE",
            msg_code=str(REMOTE_DIAGNOSE_COMMAND),
            msg_flag="0",
            xml_text=text,
            message_body=text,
            resp_str=text,
        )
        self._handle_parsed_payload(fallback)

    def _handle_parsed_payload(self, parsed: ParsedPayload) -> None:
        if parsed.message_type in ("SYSTEM_LOG_MESSAGE", "SYSTEM_LOG_DATA", "SYSTEM_CONTROL_MESSAGE", "TPS_COMMON_MESSAGE"):
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
            logging.exception("P2P stream log callback failed")

    def _on_message(self, msg_type, data_ptr, data_len, ext_ptr, ext_len) -> int:
        try:
            if msg_type == TPS_P2P_NOTIFY_SVR_LOGIN_OK:
                self._emit_status("P2P服务器登录成功")
                return 0

            if msg_type == TPS_MSG_NOTIFY_LOGIN_OK:
                logging.info("P2P login ok")
                return 0

            if msg_type == TPS_MSG_NOTIFY_LOGIN_FAILED:
                message = self._build_p2p_error(msg_type, data_ptr, data_len)
                if self._connected:
                    self._handle_disconnect(message)
                    return 0
                self._connect_error = message
                logging.warning("P2P login pre-check returned warning: %s", message)
                return 0

            if msg_type == TPS_MSG_P2P_CONNECT_OK:
                self._connected = True
                self._connect_error = ""
                self._disconnect_reason = ""
                self._connect_ready.set()
                logging.info("P2P device connected: %s", self._target_id)
                return 0

            if msg_type in P2P_FAILURE_EVENTS:
                self._handle_disconnect(self._build_p2p_error(msg_type, data_ptr, data_len))
                return 0

            if msg_type != TPS_MSG_P2P_LOG or not data_ptr or data_len == 0:
                return 0

            raw = ctypes.string_at(data_ptr, data_len)
            self._handle_transport_payload(raw)
        except Exception:
            logging.exception("P2P callback handling failed, msg_type=%s", msg_type)
        return 0

    def _handle_disconnect(self, message: str) -> None:
        message = (message or "").strip() or "P2P连接已断开"
        if self._connect_error and _is_generic_disconnect_message(message):
            message = self._connect_error
        self._connected = False
        self._connect_error = message
        self._disconnect_reason = message
        self._invalidate_interactive_command_session()
        self._connect_ready.set()
        with self._waiter_lock:
            waiter = self._active_waiter
        if waiter is not None:
            waiter.transport_error = message
            waiter.event.set()
        logging.warning("P2P transport disconnected: %s", message)

    def _on_log(self, level, message_ptr) -> None:
        if not message_ptr:
            return
        try:
            message = decode_text(ctypes.string_at(message_ptr)).strip()
        except Exception:
            return
        if message:
            logging.debug("Funclib[%s]: %s", level, message)

    @staticmethod
    def _build_p2p_error(msg_type: int, data_ptr, data_len: int) -> str:
        raw = _read_callback_payload(data_ptr, data_len)
        payload = _extract_p2p_payload_text(raw)
        error_code = _decode_p2p_error_code(raw)

        if msg_type == TPS_MSG_NOTIFY_LOGIN_FAILED:
            if _is_benign_p2p_login_return_code(error_code or 0):
                return f"P2P登录返回设备列表解析告警({error_code})"
            if payload:
                return payload
            if error_code is not None:
                return f"P2P服务登录失败({error_code})"
            return "P2P服务登录失败"
        if msg_type == TPS_MSG_P2P_OFFLINE:
            if payload and not _looks_like_device_id_text(payload):
                return payload
            if error_code is not None:
                return f"设备离线({error_code})"
            return "设备离线"
        if msg_type == TPS_MSG_NOTIFY_AUTH_FAILED:
            if payload:
                return payload
            if error_code is not None:
                return f"设备认证失败({error_code})"
            return "设备认证失败"
        if msg_type == TPS_MSG_NOTIFY_P2P_TCP_TIMEOUT:
            if payload:
                return payload
            if error_code is not None:
                return f"P2P连接超时({error_code})"
            return "P2P连接超时"
        if msg_type == TPS_MSG_NOTIFY_LOGIN_AGAIN:
            if payload:
                return payload
            if error_code is not None:
                return f"P2P登录状态失效({error_code})"
            return "P2P登录状态失效"
        if msg_type == TPS_MSG_NOTIFY_P2P_THREAD_EXIT:
            if payload and not _looks_like_device_id_text(payload):
                return payload
            if error_code is not None:
                return f"P2P会话线程已退出({error_code})"
            return "P2P会话线程已退出"
        if payload:
            return payload
        if error_code is not None:
            return f"P2P连接异常({msg_type}, {error_code})"
        return f"P2P连接异常({msg_type})"

    def _emit_status(self, message: str) -> None:
        if self._status_callback is None:
            return
        try:
            self._status_callback(message)
        except Exception:
            logging.exception("P2P status callback failed: %s", message)

    def _logout_quietly(self) -> None:
        try:
            self.lib.FC_Logout()
        except Exception:
            pass

    def close(self) -> None:
        with self._waiter_lock:
            waiter = self._active_waiter
            self._active_waiter = None
        if waiter is not None:
            waiter.transport_error = self._disconnect_reason or "连接已断开"
            waiter.event.set()

        self._logout_quietly()
        self._connected = False
        self._target_id = ""
        self._connect_error = ""
        self._disconnect_reason = ""
        self._invalidate_interactive_command_session()
        self._stream_log_listener = None
        self._stream_log_enabled = False
        self._status_callback = None

    def __enter__(self) -> "P2PDeviceSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
