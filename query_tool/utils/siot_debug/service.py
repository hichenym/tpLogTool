from __future__ import annotations

import json
import locale
import re
import subprocess
import threading
import time
import hashlib
from typing import Dict, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.logger import logger
from query_tool.utils.runtime_credential_cache import get_shared_device_query

from .config import DEFAULT_COMMAND_TIMEOUT_MS, DEVICE_USERNAME
from .models import DeviceCredentials
from .session import fetch_cloud_credentials

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_DEVICE_CONTEXT_CACHE = {}
_DEVICE_CONTEXT_CACHE_LOCK = threading.RLock()
_DEVICE_CONTEXT_CACHE_TTL_S = 5 * 60


def _is_wakeup_failed_message(message: str) -> bool:
    text = (message or "").strip().lower()
    return any(
        keyword in text
        for keyword in (
            "device wakeup timed out",
            "wakeup helper timed out",
            "wakeup helper failed",
            "唤醒失败",
            "轮唤醒失败",
        )
    )


def _normalize_user_message(message: str) -> str:
    if _is_wakeup_failed_message(message):
        return "唤醒失败"
    return str(message or "").strip()


def validate_seetong_login(username: str, password: str) -> Tuple[bool, str]:
    """校验 Seetong 账号是否可登录。"""
    username = username.strip()
    password = password.strip()
    if not username or not password:
        return False, "请输入账号和密码"

    try:
        fetch_cloud_credentials(username, password, force_refresh=True)
        return True, "验证成功"
    except Exception as exc:
        logger.error(f"Seetong 账号验证失败: {exc}")
        return False, str(exc)


def resolve_device_credentials(sn: str, env: str, username: str, password: str) -> Tuple[DeviceCredentials, Dict[str, str]]:
    """通过设备查询接口按 SN 获取设备密码，并组装调试连接所需凭据。"""
    password_digest = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
    cache_key = f"{env}|{username}|{password_digest}|{sn.strip().upper()}"
    now = time.time()
    with _DEVICE_CONTEXT_CACHE_LOCK:
        entry = _DEVICE_CONTEXT_CACHE.get(cache_key)
        if entry and (now - entry["created_at"]) < _DEVICE_CONTEXT_CACHE_TTL_S:
            context = dict(entry["context"])
            return (
                DeviceCredentials(sn=context["sn"], username=DEVICE_USERNAME, password=context["device_password"]),
                context,
            )

    query = get_shared_device_query(env, username, password)
    if query.init_error:
        raise RuntimeError(query.init_error)

    response = query.get_device_info(dev_sn=sn)
    records = response.get("data", {}).get("records", [])
    if not records:
        raise RuntimeError(f"未找到设备：{sn}")

    record = records[0]
    dev_id = str(record.get("devId") or "").strip()
    real_sn = str(record.get("devSN") or sn).strip()
    if not dev_id:
        raise RuntimeError("设备ID为空，无法获取设备密码")

    device_password = (query.get_cloud_password(dev_id) or "").strip()
    if not device_password:
        raise RuntimeError(f"未获取到设备密码：{real_sn}")

    context = {
        "sn": real_sn,
        "dev_id": dev_id,
        "device_password": device_password,
    }
    with _DEVICE_CONTEXT_CACHE_LOCK:
        _DEVICE_CONTEXT_CACHE[cache_key] = {
            "context": dict(context),
            "created_at": now,
        }

    return (
        DeviceCredentials(sn=real_sn, username=DEVICE_USERNAME, password=device_password),
        context,
    )


class SiotDebugWorker(QObject):
    """运行在后台线程中的 SIOT 调试工作器。"""

    status_message = pyqtSignal(str)
    connected = pyqtSignal(dict)
    disconnected = pyqtSignal(str)
    connect_failed = pyqtSignal(str)
    command_output = pyqtSignal(str)
    stream_log_output = pyqtSignal(str)
    command_progress = pyqtSignal(str, str)
    command_failed = pyqtSignal(str)
    command_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._process = None
        self._reader_thread = None
        self._context = {}
        self._connected = False
        self._closing = False
        self._pending_context = None
        self._cancel_connect_event = threading.Event()

    @pyqtSlot(str, str, str, str, str, str)
    def connect_with_accounts(
        self,
        sn: str,
        env: str,
        device_username: str,
        device_password: str,
        seetong_username: str,
        seetong_password: str,
    ):
        try:
            self._cancel_connect_event.clear()
            self._close_process(wait=True)
            if self._is_connect_cancelled():
                return
            self.status_message.emit("正在查询设备密码...")
            credentials, context = resolve_device_credentials(sn, env, device_username, device_password)
            if self._is_connect_cancelled():
                return
            self.status_message.emit(f"已获取设备密码，目标设备: {context['sn']}")

            process = subprocess.Popen(
                build_internal_command("--siot-subprocess-runner"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,  # 使用二进制模式，避免自动解码问题
                bufsize=1,
            )

            self._process = process
            self._connected = False
            self._closing = False
            self._pending_context = context

            if self._is_connect_cancelled():
                self._close_process(wait=False)
                return

            self._reader_thread = threading.Thread(
                target=self._read_process_output,
                name="siot-debug-reader",
                daemon=True,
            )
            self._reader_thread.start()

            if self._is_connect_cancelled():
                self._close_process(wait=False)
                return

            self._send_to_process(
                {
                    "action": "connect",
                    "cloud": {
                        "username": seetong_username,
                        "password": seetong_password,
                    },
                    "device": {
                        "sn": credentials.sn,
                        "username": credentials.username,
                        "password": credentials.password,
                    },
                }
            )
        except Exception as exc:
            if self._is_connect_cancelled():
                self._close_process(wait=False)
                return
            logger.error(f"连接调试设备失败: {exc}")
            self._close_process(wait=True)
            self.connect_failed.emit(_normalize_user_message(str(exc)))

    @pyqtSlot(str, int, str)
    def execute_command(self, command: str, timeout_ms: int = DEFAULT_COMMAND_TIMEOUT_MS, download_root: str = ""):
        command = command.strip()
        if not command:
            self.command_finished.emit()
            return

        if self._process is None or self._process.poll() is not None or not self._connected:
            self.command_failed.emit("设备尚未连接，请先登录。")
            self.command_finished.emit()
            return

        try:
            self._send_to_process(
                {
                    "action": "command",
                    "command": command,
                    "timeout_ms": timeout_ms,
                    "download_root": download_root or "",
                }
            )
        except Exception as exc:
            logger.error(f"发送调试命令失败: {exc}")
            self.command_failed.emit(str(exc))
            self.command_finished.emit()

    @pyqtSlot()
    def disconnect_device(self):
        if self._process is None or self._process.poll() is not None:
            self._connected = False
            self.disconnected.emit("连接已断开")
            return

        self._close_process(wait=False)
        self._connected = False
        self.disconnected.emit("连接已断开")

    @pyqtSlot()
    def shutdown(self):
        self._close_process(wait=False)

    def cancel_pending_connect(self):
        self._cancel_connect_event.set()
        if not self._connected:
            self._close_process(wait=False)

    def _read_process_output(self):
        process = self._process
        if process is None or process.stdout is None:
            return

        try:
            # 获取系统默认编码，用于正确读取子进程输出
            encoding = locale.getpreferredencoding(False)
            for raw_line in iter(process.stdout.readline, b''):
                try:
                    line = raw_line.decode(encoding).strip()
                except UnicodeDecodeError:
                    # 如果解码失败，尝试使用 GBK（Windows 中文环境常见）
                    try:
                        line = raw_line.decode('gbk').strip()
                    except UnicodeDecodeError:
                        # 如果还是失败，跳过这一行
                        continue
                line = self._sanitize_output_line(line)
                if not line:
                    continue
                if self._should_ignore_output_line(line):
                    continue
                self._handle_process_line(line)
        except Exception as exc:
            logger.error(f"读取调试子进程输出失败: {exc}")
        finally:
            if process is not self._process:
                return

            return_code = None
            if process is not None:
                try:
                    return_code = process.poll()
                except Exception:
                    return_code = None

            self._process = None

            was_connected = self._connected
            closing = self._closing
            self._connected = False
            self._context = {}
            self._pending_context = None

            if self._is_connect_cancelled():
                return

            if closing:
                self._closing = False
                return

            if was_connected:
                self.disconnected.emit("连接已断开")
            elif return_code not in (0, None):
                self.connect_failed.emit("failed to connect signaling server")

    def _handle_process_line(self, line: str):
        line = self._sanitize_output_line(line)
        if not line or self._should_ignore_output_line(line):
            return

        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            if self._is_connect_cancelled() and not self._connected:
                return
            self.command_output.emit(line)
            return

        event = payload.get("event")
        raw_message = str(payload.get("message") or "")
        message = _normalize_user_message(raw_message)

        if self._is_connect_cancelled() and not self._connected:
            if event == "connected":
                self._close_process(wait=False)
            return

        if event == "status":
            self.status_message.emit(_normalize_user_message(raw_message))
            return

        if event == "output":
            if payload.get("stream_log"):
                self.stream_log_output.emit(message)
            else:
                self.command_output.emit(message)
            return

        if event == "progress":
            self.command_progress.emit(str(payload.get("progress_id") or ""), message)
            return

        if event == "command_failed":
            self.command_failed.emit(message)
            return

        if event == "command_finished":
            self.command_finished.emit()
            return

        if event == "connected":
            self._connected = True
            self._context = self._pending_context or {}
            self.connected.emit(self._context)
            self._closing = False
            return

        if event == "connect_failed":
            self._connected = False
            self.connect_failed.emit(message)
            self._close_process(wait=False)
            return

        if event == "disconnected":
            self._connected = False
            self.disconnected.emit(message or "连接已断开")
            self._close_process(wait=False)

    def _is_connect_cancelled(self) -> bool:
        return self._cancel_connect_event.is_set()

    @staticmethod
    def _sanitize_output_line(line: str) -> str:
        line = ANSI_ESCAPE_RE.sub("", line or "")
        return line.replace("\r", "").strip()

    @staticmethod
    def _should_ignore_output_line(line: str) -> bool:
        lowered = (line or "").strip().lower()
        if not lowered:
            return True
        if lowered.startswith("mem: calloc(") and lowered.endswith("ok"):
            return True
        return False

    def _send_to_process(self, payload: dict):
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("调试会话未启动")
        # 将 JSON 字符串编码为字节后写入
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode('utf-8')
        self._process.stdin.write(data)
        self._process.stdin.flush()

    def _close_process(self, wait: bool):
        process = self._process
        self._process = None
        self._connected = False
        self._pending_context = None
        self._context = {}

        if process is None:
            self._closing = False
            return

        self._closing = True

        try:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass

            if wait:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            else:
                if process.poll() is None:
                    process.kill()
        except Exception as exc:
            logger.warning(f"关闭调试子进程失败: {exc}")
        finally:
            self._closing = False
