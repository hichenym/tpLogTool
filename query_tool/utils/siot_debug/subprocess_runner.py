from __future__ import annotations

import json
import logging
import re
import shlex
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from .command_catalog import is_getsystemcfg_command, is_startlogp2p_command, is_syscmd_family_command, is_syscmdex_command, parse_startlogp2p_level
from .config import APP_LOG_DIR, DEFAULT_COMMAND_TIMEOUT_MS, RUN_LOG_PATH
from .models import CommandResult, DeviceCredentials, TransferProgress
from .session import DeviceSession

CONNECT_WAKEUP_ATTEMPTS = 1
STREAM_LOG_FLUSH_INTERVAL_S = 0.2
STREAM_LOG_MAX_BATCH = 50
class _StreamLogEmitter:
    def __init__(self):
        self._lock = threading.Lock()
        self._buffer = []
        self._last_flush_at = 0.0
        self._file_path = None
        self._file_handle = None

    def start(self, device_sn: str, download_root: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_sn = (device_sn or "unknown").strip() or "unknown"
        root = Path(download_root).expanduser() if (download_root or "").strip() else APP_LOG_DIR
        stream_log_dir = root / safe_sn
        stream_log_dir.mkdir(parents=True, exist_ok=True)
        self.stop(flush=False)
        self._file_path = stream_log_dir / f"{safe_sn}_serial_{timestamp}.log"
        self._file_handle = self._file_path.open("a", encoding="utf-8", buffering=1)
        self._last_flush_at = 0.0
        return str(self._file_path)

    def emit(self, message: str):
        text = str(message or "").strip()
        if not text:
            return
        payload = None
        now = time.monotonic()
        self._write_lines(text)
        with self._lock:
            self._buffer.append(text)
            if len(self._buffer) >= STREAM_LOG_MAX_BATCH or (now - self._last_flush_at) >= STREAM_LOG_FLUSH_INTERVAL_S:
                payload = "\n".join(self._buffer)
                self._buffer.clear()
                self._last_flush_at = now
        if payload:
            _emit("output", message=payload, stream_log=True)

    def flush(self):
        payload = None
        with self._lock:
            if self._buffer:
                payload = "\n".join(self._buffer)
                self._buffer.clear()
                self._last_flush_at = time.monotonic()
        if payload:
            _emit("output", message=payload, stream_log=True)

    def stop(self, flush: bool = True):
        if flush:
            self.flush()
        file_path = self._file_path
        handle = self._file_handle
        self._file_handle = None
        self._file_path = None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        return str(file_path) if file_path else ""

    def _write_lines(self, text: str):
        handle = self._file_handle
        if handle is None:
            return
        try:
            handle.write(text + "\n")
        except Exception:
            logging.exception("Write stream log file failed")


_STREAM_LOG_EMITTER = _StreamLogEmitter()


def _configure_runtime_logging():
    APP_LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(str(RUN_LOG_PATH), encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s:%(name)s:%(message)s",
            datefmt="%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)


def _emit(event: str, **payload):
    message = {"event": event}
    message.update(payload)
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _format_file_progress(progress: TransferProgress) -> str:
    filename = progress.filename or "(unknown)"
    size_kb = progress.received_bytes / 1024
    return f"正在下载 {filename}: {size_kb:.1f} kb，包#{progress.packet_index}"


class _ProgressEmitter:
    """限制文件下载进度输出频率，避免大量 UI 刷新导致卡顿。"""

    def __init__(self, progress_id: str, total_bytes: int = 0):
        self.progress_id = progress_id
        self.total_bytes = max(int(total_bytes or 0), 0)
        self._last_emit_at = 0.0
        self._last_packet_index = 0
        self._last_bucket = -1

    def emit(self, progress: TransferProgress):
        now = time.monotonic()
        if self.total_bytes > 0:
            bucket = min(10, int(progress.received_bytes * 10 / max(self.total_bytes, 1)))
            should_emit = progress.finished or bucket != self._last_bucket
        else:
            bucket = -1
            should_emit = (
                progress.finished
                or progress.packet_index <= 1
                or progress.packet_index - self._last_packet_index >= 32
                or now - self._last_emit_at >= 0.5
            )
        if not should_emit:
            return

        self._last_emit_at = now
        self._last_packet_index = progress.packet_index
        self._last_bucket = bucket
        _emit(
            "progress",
            progress_id=self.progress_id,
            message=self._format_progress_text(progress),
        )

    def _format_progress_text(self, progress: TransferProgress) -> str:
        filename = progress.filename or "(unknown)"
        if self.total_bytes > 0:
            current = min(progress.received_bytes, self.total_bytes)
            filled = min(10, int(current * 10 / max(self.total_bytes, 1)))
            bar = "#" * filled + "-" * (10 - filled)
            return f"{filename} [{bar}] {self._format_size(current)}/{self._format_size(self.total_bytes)}"
        return _format_file_progress(progress)

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1024:
            return f"{size / 1024:.1f}kb"
        return f"{size}b"


def _format_command_result(command: str, result: CommandResult) -> str:
    if is_getsystemcfg_command(command) and _is_missing_file_result(command, result):
        return _format_missing_file_message(command, result)

    if is_getsystemcfg_command(command):
        return ""

    if result.display_text:
        return result.display_text

    if result.success and result.streamed_packets:
        filename = result.filename or command.split(maxsplit=1)[-1]
        return (
            f"文件接收完成: {filename}, 总长度={result.received_bytes} 字节, "
            f"共 {result.streamed_packets} 个数据包。"
        )

    if result.success and result.acknowledged:
        if command.lower() in ("syscmd start", "syscmdex start"):
            return ""
        return "命令已发送成功，设备未返回内容"

    return "无返回内容。"


def _resolve_output_filename(command: str, result: CommandResult) -> str:
    candidate = (result.filename or "").strip()
    if not candidate:
        parts = command.split(maxsplit=1)
        candidate = parts[1].strip() if len(parts) > 1 else "download.bin"
    return Path(candidate).name or "download.bin"


def _save_getsystemcfg_file(command: str, result: CommandResult, download_root: str, device_sn: str) -> str:
    if not result.binary_payload:
        return ""

    root = Path(download_root).expanduser()
    sn_dir = root / device_sn
    sn_dir.mkdir(parents=True, exist_ok=True)
    file_path = sn_dir / _resolve_output_filename(command, result)
    file_path.write_bytes(result.binary_payload)
    return str(file_path)


def _extract_getsystemcfg_path(command: str) -> str:
    parts = command.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


def _is_missing_file_result(command: str, result: CommandResult) -> bool:
    if not is_getsystemcfg_command(command):
        return False
    text = (result.display_text or "").strip().lower()
    return text == "file fail" or "file fail" in text


def _format_missing_file_message(command: str, result: CommandResult) -> str:
    filename = _resolve_output_filename(command, result)
    return f"{filename} 不存在"


def _is_wakeup_failed_message(message: str) -> bool:
    text = (message or "").strip().lower()
    return any(
        keyword in text
        for keyword in (
            "device wakeup timed out",
            "wakeup helper timed out",
            "wakeup helper failed",
            "唤醒失败",
        )
    )


def _try_probe_file_size(session: DeviceSession, command: str) -> int:
    file_path = _extract_getsystemcfg_path(command)
    if not file_path:
        return 0

    quoted_path = shlex.quote(file_path)
    probe_commands = (
        f"syscmd stat -c %s -- {quoted_path}",
        f"syscmd wc -c < {quoted_path}",
    )
    for probe_command in probe_commands:
        try:
            result = session.execute_command(probe_command, timeout_ms=5000, progress_callback=None)
        except Exception:
            continue
        text = (result.display_text or "").strip()
        match = re.search(r"(\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return 0


def _handle_command(session: DeviceSession, payload: dict):
    command = str(payload.get("command") or "").strip()
    timeout_ms = int(payload.get("timeout_ms") or DEFAULT_COMMAND_TIMEOUT_MS)
    download_root = str(payload.get("download_root") or "").strip()

    if not command:
        _emit("command_finished")
        return

    if not (is_syscmd_family_command(command) or is_getsystemcfg_command(command) or is_startlogp2p_command(command)):
        _emit("command_failed", message="当前仅支持 syscmd / syscmdEx / GetSystemCfg / startlogp2p 命令。")
        _emit("command_finished")
        return

    try:
        stream_log_level = parse_startlogp2p_level(command)
        stream_log_path = ""
        if is_startlogp2p_command(command) and stream_log_level and stream_log_level != 0:
            stream_log_path = _STREAM_LOG_EMITTER.start(
                session.device.sn if session.device else "unknown",
                download_root,
            )
            if stream_log_path:
                _emit("output", message=f"已开启 P2P 实时日志监听，开始写入: {stream_log_path}")
            else:
                _emit("output", message="已开启 P2P 实时日志监听")
        total_bytes = _try_probe_file_size(session, command) if is_getsystemcfg_command(command) else 0
        progress_emitter = _ProgressEmitter(
            progress_id=f"{command}:{time.monotonic_ns()}",
            total_bytes=total_bytes,
        )
        result = session.execute_command(
            command,
            timeout_ms=timeout_ms,
            progress_callback=progress_emitter.emit,
            stream_log_callback=_STREAM_LOG_EMITTER.emit,
        )
        if not is_startlogp2p_command(command) or stream_log_level == 0:
            _STREAM_LOG_EMITTER.flush()
        if _is_missing_file_result(command, result):
            _emit("command_failed", message=_format_missing_file_message(command, result))
            return
        if is_getsystemcfg_command(command) and download_root and result.binary_payload:
            saved_path = _save_getsystemcfg_file(
                command,
                result,
                download_root=download_root,
                device_sn=session.device.sn if session.device else "",
            )
            if saved_path:
                _emit("output", message=f"文件已下载到: {saved_path}")
        message = _format_command_result(command, result)
        if message:
            _emit("output", message=message)
        if is_startlogp2p_command(command):
            if stream_log_level is None:
                _emit("command_failed", message="startlogp2p 参数无效，支持 0 / 8 / 12 / 16 / 24 / 31。")
                return
            if stream_log_level == 0:
                saved_log_path = _STREAM_LOG_EMITTER.stop(flush=True)
                if saved_log_path:
                    _emit("output", message=f"已关闭 P2P 实时日志监听，保存成功：{saved_log_path}")
                else:
                    _emit("output", message="已关闭 P2P 实时日志监听")
    except Exception as exc:
        _STREAM_LOG_EMITTER.flush()
        _emit("command_failed", message=str(exc))
    finally:
        if not is_startlogp2p_command(command) or stream_log_level == 0:
            _STREAM_LOG_EMITTER.flush()
        _emit("command_finished")


def main():
    session = None
    connected = False

    try:
        _configure_runtime_logging()
        first_line = sys.stdin.readline()
        if not first_line:
            return 1

        first_payload = json.loads(first_line)
        if first_payload.get("action") != "connect":
            _emit("connect_failed", message="invalid initial action")
            return 2

        cloud = first_payload.get("cloud") or {}
        device = first_payload.get("device") or {}
        credentials = DeviceCredentials(
            sn=str(device.get("sn") or "").strip(),
            username=str(device.get("username") or "").strip(),
            password=str(device.get("password") or "").strip(),
        )

        cloud_username = str(cloud.get("username") or "").strip()
        cloud_password = str(cloud.get("password") or "").strip()
        wakeup_failures = []
        last_connect_error = ""

        for attempt in range(1, CONNECT_WAKEUP_ATTEMPTS + 1):
            session = DeviceSession(cloud_username, cloud_password)
            try:
                session.connect(credentials, status_callback=lambda msg: _emit("status", message=msg))
                connected = True
                _emit("connected")
                break
            except Exception as exc:
                last_connect_error = str(exc)
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        pass
                    session = None

                if not _is_wakeup_failed_message(last_connect_error):
                    raise

                wakeup_failures.append(f"第{attempt}轮唤醒失败")
                if attempt < CONNECT_WAKEUP_ATTEMPTS:
                    _emit("status", message=f"第{attempt}轮唤醒失败，准备第{attempt + 1}轮重试...")
                    continue
                raise RuntimeError("\n".join(wakeup_failures) or "唤醒失败")

        if not connected:
            raise RuntimeError(last_connect_error or "登录设备失败")

        while True:
            line = sys.stdin.readline()
            if not line:
                break

            payload = json.loads(line)
            action = payload.get("action")

            if action == "command":
                _handle_command(session, payload)
                continue

            if action in ("disconnect", "shutdown"):
                break

        return 0
    except Exception as exc:
        event = "connect_failed" if not connected else "command_failed"
        _emit(event, message=str(exc))
        if connected:
            _emit("command_finished")
        return 1
    finally:
        if session is not None:
            try:
                _STREAM_LOG_EMITTER.stop(flush=True)
                session.close()
            except Exception:
                pass
        if connected:
            _emit("disconnected", message="连接已断开")


if __name__ == "__main__":
    raise SystemExit(main())
