"""
日志批量拉取页面
"""
from __future__ import annotations

import html
import os
import re
import json
import locale
import queue
import subprocess
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from PyQt5.QtCore import QPointF, QRectF, QSize, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QIcon, QTextDocument
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import StyleManager, config_manager, get_account_config, get_seetong_account_config
from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.logger import logger
from query_tool.utils.siot_debug import DEFAULT_COMMAND_TIMEOUT_MS, is_getsystemcfg_command, is_syscmd_family_command
from query_tool.utils.siot_debug.service import resolve_device_credentials
from query_tool.utils.theme_manager import t
from query_tool.widgets import PlainTextEdit, prompt_configure_account


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
RICH_TEXT_ROLE = Qt.UserRole + 1


class PathDisplayLabel(QLabel):
    """支持双击打开目录的路径标签。"""

    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class CommandPlainTextEdit(PlainTextEdit):
    """命令文本框，支持失焦回调。"""

    focus_lost = pyqtSignal()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()


class RichTextItemDelegate(QStyledItemDelegate):
    """支持按行着色的表格委托。"""

    def paint(self, painter, option, index):
        segments = index.data(RICH_TEXT_ROLE)
        if not segments:
            super().paint(painter, option, index)
            return

        option_copy = option
        self.initStyleOption(option_copy, index)
        option_copy.text = ""

        style = option.widget.style() if option.widget else None
        if style is None:
            style = self.parent().style() if self.parent() is not None else None
        if style is not None:
            style.drawControl(QStyle.CE_ItemViewItem, option_copy, painter, option.widget)

        document = QTextDocument()
        document.setDefaultFont(option.font)
        document.setDocumentMargin(2)
        document.setHtml(self._segments_to_html(segments))
        document.setTextWidth(max(0, option.rect.width() - 6))

        painter.save()
        try:
            painter.translate(option.rect.topLeft() + QPointF(3, 1))
            clip_rect = QRectF(
                0,
                0,
                max(0, option.rect.width() - 6),
                max(0, option.rect.height() - 2),
            )
            document.drawContents(painter, clip_rect)
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        segments = index.data(RICH_TEXT_ROLE)
        if not segments:
            return super().sizeHint(option, index)

        document = QTextDocument()
        document.setDefaultFont(option.font)
        document.setDocumentMargin(2)
        document.setHtml(self._segments_to_html(segments))

        width = option.rect.width()
        if width <= 0 and option.widget is not None:
            width = option.widget.columnWidth(index.column())
        document.setTextWidth(max(40, width - 6))
        return document.size().toSize()

    @staticmethod
    def _segments_to_html(segments):
        lines = []
        for segment in segments:
            text = html.escape(str(segment.get("text") or " "))
            color = str(segment.get("color") or t("text_primary"))
            lines.append(f'<div style="color: {color}; white-space: pre-wrap;">{text}</div>')
        return "".join(lines)


class BatchLogFetchThread(QThread):
    """批量拉日志线程。"""

    device_updated = pyqtSignal(dict)
    summary_ready = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        sn_list,
        commands,
        download_root,
        env,
        device_username,
        device_password,
        seetong_username,
        seetong_password,
        max_workers=20,
        timeout_ms=DEFAULT_COMMAND_TIMEOUT_MS,
    ):
        super().__init__()
        self.sn_list = list(sn_list)
        self.commands = list(commands)
        self.download_root = str(download_root)
        self.env = env
        self.device_username = device_username
        self.device_password = device_password
        self.seetong_username = seetong_username
        self.seetong_password = seetong_password
        self.max_workers = max(1, int(max_workers or 20))
        self.timeout_ms = int(timeout_ms or DEFAULT_COMMAND_TIMEOUT_MS)
        self._stop_event = threading.Event()
        self._process_lock = threading.Lock()
        self._active_processes = set()
        self._executor = None

    def cancel(self):
        self._stop_event.set()
        with self._process_lock:
            processes = list(self._active_processes)
        for process in processes:
            try:
                self._terminate_process_nowait(process)
            except Exception:
                pass
        if self._executor is not None:
            try:
                self._executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def run(self):
        started_at = time.monotonic()
        total = len(self.sn_list)
        success_devices = 0
        partial_devices = 0
        failed_devices = 0
        total_files = 0

        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._executor = executor
        pending_futures = set()
        try:
            pending_futures = {
                executor.submit(self._process_single_device, sn)
                for sn in self.sn_list
            }
            while pending_futures and not self._stop_event.is_set():
                done_futures, pending_futures = wait(
                    pending_futures,
                    timeout=0.2,
                    return_when=FIRST_COMPLETED,
                )
                for future in done_futures:
                    result = future.result()
                    total_files += int(result.get("success_count") or 0)
                    if result.get("status") == "完成":
                        success_devices += 1
                    elif result.get("status") == "部分完成":
                        partial_devices += 1
                    else:
                        failed_devices += 1
        except Exception as exc:
            if self._stop_event.is_set():
                return
            logger.error(f"批量拉日志失败: {exc}")
            self.error_signal.emit(str(exc))
            return
        finally:
            if self._stop_event.is_set():
                for future in pending_futures:
                    future.cancel()
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self._executor = None

        if self._stop_event.is_set():
            self.summary_ready.emit(
                {
                    "total": total,
                    "success_devices": success_devices,
                    "partial_devices": partial_devices,
                    "failed_devices": failed_devices,
                    "total_files": total_files,
                    "duration_seconds": max(0.0, time.monotonic() - started_at),
                    "cancelled": True,
                }
            )
            return

        self.summary_ready.emit(
            {
                "total": total,
                "success_devices": success_devices,
                "partial_devices": partial_devices,
                "failed_devices": failed_devices,
                "total_files": total_files,
                "duration_seconds": max(0.0, time.monotonic() - started_at),
                "cancelled": False,
            }
        )

    def _process_single_device(self, sn: str):
        if self._stop_event.is_set():
            return {
                "sn": sn,
                "status": "已取消",
                "success_count": 0,
                "failed_count": 0,
                "files": [],
                "detail": "已取消",
            }
        success_count = 0
        failed_count = 0
        file_entries = []
        details = []
        connect_details = []
        connected_ok = False

        self._emit_device(sn, "查询设备密码中", success_count, failed_count, file_entries, "正在获取设备密码")
        try:
            credentials, _ = resolve_device_credentials(
                sn,
                self.env,
                self.device_username,
                self.device_password,
            )
        except Exception as exc:
            if self._stop_event.is_set():
                return self._build_cancelled_result(sn, success_count, failed_count, file_entries)
            normalized_message = self._normalize_error_detail(str(exc))
            detail_message = "设备离线" if self._is_device_offline_message(normalized_message) else normalized_message
            status_text = self._map_failure_status(normalized_message)
            self._emit_device(sn, status_text, success_count, failed_count + 1, file_entries, detail_message)
            return {
                "sn": sn,
                "status": status_text,
                "success_count": success_count,
                "failed_count": failed_count + 1,
                "files": file_entries,
                "detail": detail_message,
            }

        if self._stop_event.is_set():
            self._emit_device(sn, "已取消", success_count, failed_count, file_entries, "已取消")
            return {
                "sn": sn,
                "status": "已取消",
                "success_count": success_count,
                "failed_count": failed_count,
                "files": file_entries,
                "detail": "已取消",
            }

        self._emit_device(sn, "连接设备中", success_count, failed_count, file_entries, "正在登录设备")
        process = None
        event_queue = None
        try:
            process, event_queue = self._start_process(credentials)
            self._wait_for_connect(
                event_queue,
                status_callback=lambda text: self._on_connect_status(
                    sn,
                    text,
                    connect_details,
                    success_count,
                    failed_count,
                    file_entries,
                ),
            )
            connected_ok = True

            for index, raw_command in enumerate(self.commands, 1):
                if self._stop_event.is_set():
                    break
                command = self._normalize_command(raw_command)
                if not command:
                    continue

                self._emit_device(
                    sn,
                    f"执行中 {index}/{len(self.commands)}",
                    success_count,
                    failed_count,
                    file_entries,
                    f"执行命令: {command}",
                )

                try:
                    command_result = self._run_command(process, event_queue, command)
                    if is_getsystemcfg_command(command):
                        if command_result.get("saved_file"):
                            file_entries.append(command_result["saved_file"])
                            success_count += 1
                            details.append(f"{command_result['saved_file']}: 成功")
                        else:
                            failed_count += 1
                            target_name = self._resolve_requested_name(command)
                            if command_result.get("missing_file"):
                                file_entries.append(f"{command_result['missing_file']} 不存在")
                            else:
                                file_entries.append(f"{target_name} 获取失败")
                            details.append(f"{command}: {command_result.get('message') or '获取失败'}")
                    else:
                        if command_result.get("success"):
                            details.append(f"{command}: {command_result.get('message') or '已执行'}")
                        else:
                            failed_count += 1
                            details.append(f"{command}: {command_result.get('message') or '执行失败'}")
                except Exception as exc:
                    failed_count += 1
                    details.append(f"{command}: {exc}")

                self._emit_device(
                    sn,
                    f"执行中 {index}/{len(self.commands)}",
                    success_count,
                    failed_count,
                    file_entries,
                    "\n".join(details),
                )
        except Exception as exc:
            if self._stop_event.is_set():
                return self._build_cancelled_result(sn, success_count, failed_count, file_entries)
            normalized_message = self._normalize_error_detail(str(exc))
            detail_message = "设备离线" if self._is_device_offline_message(normalized_message) else normalized_message
            status_text = self._map_failure_status(normalized_message)
            if status_text in ("唤醒失败", "设备离线"):
                detail_lines = [detail_message]
            else:
                detail_lines = list(connect_details)
                self._append_unique_detail(detail_lines, detail_message)
            self._emit_device(sn, status_text, success_count, failed_count + 1, file_entries, "\n".join(detail_lines))
            return {
                "sn": sn,
                "status": status_text,
                "success_count": success_count,
                "failed_count": failed_count + 1,
                "files": file_entries,
                "detail": "\n".join(detail_lines),
            }
        finally:
            if process is not None and connected_ok:
                try:
                    self._emit_device(sn, "正在注销", success_count, failed_count, file_entries, "\n".join(details) or "正在断开设备连接")
                    self._send_payload(process, {"action": "disconnect"})
                    self._drain_until_disconnected(event_queue, timeout_s=5.0)
                except Exception as exc:
                    logger.warning(f"关闭日志设备子进程失败 {sn}: {exc}")
                finally:
                    self._close_process(process)
                    time.sleep(0.2)

        if self._stop_event.is_set():
            return self._build_cancelled_result(sn, success_count, failed_count, file_entries)

        if success_count > 0 and failed_count == 0:
            final_status = "完成"
        elif success_count > 0:
            final_status = "部分完成"
        else:
            final_status = "失败"

        final_detail = "\n".join(details) if details else "执行完成"
        self._emit_device(sn, final_status, success_count, failed_count, file_entries, final_detail)
        return {
            "sn": sn,
            "status": final_status,
            "success_count": success_count,
            "failed_count": failed_count,
            "files": file_entries,
            "detail": final_detail,
        }

    def _emit_device(self, sn, status, success_count, failed_count, files, detail):
        self.device_updated.emit(
            {
                "sn": sn,
                "status": status,
                "success_count": success_count,
                "failed_count": failed_count,
                "files": list(files),
                "detail": detail,
            }
        )

    def _build_cancelled_result(self, sn, success_count, failed_count, files):
        self._emit_device(sn, "已取消", success_count, failed_count, files, "已取消")
        return {
            "sn": sn,
            "status": "已取消",
            "success_count": success_count,
            "failed_count": failed_count,
            "files": list(files),
            "detail": "已取消",
        }

    def _save_download_file(self, sn: str, command: str, filename: str, payload: bytes) -> str:
        root = Path(self.download_root).expanduser()
        sn_dir = root / sn
        sn_dir.mkdir(parents=True, exist_ok=True)
        output_name = self._resolve_output_filename(command, filename)
        file_path = sn_dir / output_name
        file_path.write_bytes(payload)
        return str(file_path)

    @staticmethod
    def _resolve_output_filename(command: str, filename: str) -> str:
        candidate = (filename or "").strip()
        if not candidate:
            parts = command.split(maxsplit=1)
            candidate = parts[1].strip() if len(parts) > 1 else "download.bin"
        return Path(candidate).name or "download.bin"

    @classmethod
    def _resolve_requested_name(cls, command: str) -> str:
        return cls._resolve_output_filename(command, "")

    @staticmethod
    def _normalize_command(command: str) -> str:
        command = (command or "").strip()
        if not command:
            return ""
        if is_getsystemcfg_command(command) or is_syscmd_family_command(command):
            return command
        return f"GetSystemCfg {command}"

    def _start_process(self, credentials):
        process = subprocess.Popen(
            build_internal_command("--siot-subprocess-runner"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=1,
        )
        event_queue = queue.Queue()
        reader = threading.Thread(
            target=self._read_process_output,
            args=(process, event_queue),
            name=f"log-fetch-{credentials.sn}",
            daemon=True,
        )
        reader.start()
        with self._process_lock:
            self._active_processes.add(process)
        self._send_payload(
            process,
            {
                "action": "connect",
                "cloud": {
                    "username": self.seetong_username,
                    "password": self.seetong_password,
                },
                "device": {
                    "sn": credentials.sn,
                    "username": credentials.username,
                    "password": credentials.password,
                },
            },
        )
        return process, event_queue

    def _wait_for_connect(self, event_queue, status_callback=None):
        deadline = time.monotonic() + 35.0
        last_status = ""
        saw_wakeup = False
        while time.monotonic() < deadline:
            event = self._get_next_event(event_queue, max(0.1, deadline - time.monotonic()))
            event_name = event.get("event")
            if event_name == "status":
                last_status = str(event.get("message") or "")
                if "唤醒" in last_status:
                    saw_wakeup = True
                if callable(status_callback):
                    status_callback(last_status)
                if self._is_device_offline_message(last_status):
                    raise RuntimeError("设备离线")
                continue
            if event_name == "connected":
                return
            if event_name == "connect_failed":
                message = str(event.get("message") or "登录失败")
                if self._is_wakeup_failed_message(message) or saw_wakeup:
                    raise RuntimeError("唤醒失败")
                raise RuntimeError(message)
            if event_name == "disconnected":
                message = str(event.get("message") or last_status or "连接已断开")
                if self._is_wakeup_failed_message(message) or saw_wakeup:
                    raise RuntimeError("唤醒失败")
                raise RuntimeError(message)
            if event_name == "eof":
                if self._is_wakeup_failed_message(last_status) or saw_wakeup:
                    raise RuntimeError("唤醒失败")
                raise RuntimeError(last_status or "登录设备失败")
        if self._is_wakeup_failed_message(last_status) or saw_wakeup:
            raise RuntimeError("唤醒失败")
        raise RuntimeError(last_status or "登录设备超时")

    def _run_command(self, process, event_queue, command: str):
        self._send_payload(
            process,
            {
                "action": "command",
                "command": command,
                "timeout_ms": self.timeout_ms,
                "download_root": self.download_root,
            },
        )

        deadline = time.monotonic() + (self.timeout_ms / 1000.0) + 5.0
        message = ""
        saved_file = ""
        failed_message = ""
        missing_file = ""
        while time.monotonic() < deadline:
            event = self._get_next_event(event_queue, max(0.1, deadline - time.monotonic()))
            event_name = event.get("event")
            if event_name in ("status", "progress"):
                continue
            if event_name == "output":
                current = str(event.get("message") or "")
                if current.startswith("文件已下载到:"):
                    saved_path = current.split(":", 1)[1].strip()
                    saved_file = str(Path(saved_path).name)
                    message = current
                elif current:
                    message = current
                continue
            if event_name == "command_failed":
                failed_message = str(event.get("message") or "执行失败")
                if is_getsystemcfg_command(command) and self._is_missing_file_message(failed_message):
                    missing_file = self._resolve_requested_name(command)
                continue
            if event_name == "command_finished":
                return {
                    "success": not bool(failed_message),
                    "message": failed_message or message,
                    "saved_file": saved_file,
                    "missing_file": missing_file,
                }
            if event_name == "disconnected":
                raise RuntimeError(str(event.get("message") or "连接已断开"))
            if event_name == "connect_failed":
                raise RuntimeError(str(event.get("message") or "登录失败"))
            if event_name == "eof":
                raise RuntimeError(failed_message or message or "命令执行中断")
        raise RuntimeError("命令执行超时")

    def _drain_until_disconnected(self, event_queue, timeout_s: float):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            event = self._get_next_event(event_queue, max(0.1, deadline - time.monotonic()))
            if event.get("event") in ("disconnected", "eof"):
                return

    @staticmethod
    def _send_payload(process, payload: dict):
        if process is None or process.stdin is None:
            raise RuntimeError("日志子进程未启动")
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        process.stdin.write(data)
        process.stdin.flush()

    def _close_process(self, process):
        if process is None:
            return
        try:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        except Exception:
            pass
        finally:
            with self._process_lock:
                self._active_processes.discard(process)

    def _terminate_process_nowait(self, process):
        if process is None:
            return
        try:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            if process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
        finally:
            with self._process_lock:
                self._active_processes.discard(process)

    @staticmethod
    def _get_next_event(event_queue, timeout_s: float):
        try:
            return event_queue.get(timeout=max(timeout_s, 0.1))
        except queue.Empty as exc:
            raise RuntimeError("等待设备响应超时") from exc

    @classmethod
    def _read_process_output(cls, process, event_queue):
        if process is None or process.stdout is None:
            event_queue.put({"event": "eof"})
            return

        encoding = locale.getpreferredencoding(False)
        try:
            for raw_line in iter(process.stdout.readline, b""):
                if not raw_line:
                    break
                line = cls._decode_raw_line(raw_line, encoding)
                line = cls._sanitize_output_line(line)
                if not line or cls._should_ignore_output_line(line):
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    payload = {"event": "output", "message": line}
                event_queue.put(payload)
        finally:
            event_queue.put({"event": "eof"})

    @staticmethod
    def _decode_raw_line(raw_line: bytes, encoding: str) -> str:
        try:
            return raw_line.decode(encoding).strip()
        except UnicodeDecodeError:
            try:
                return raw_line.decode("gbk").strip()
            except UnicodeDecodeError:
                return raw_line.decode("utf-8", errors="ignore").strip()

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

    @staticmethod
    def _is_device_offline_message(message: str) -> bool:
        message = (message or "").strip()
        return "不在线" in message or "设备离线" in message

    @staticmethod
    def _is_missing_file_message(message: str) -> bool:
        message = (message or "").strip().lower()
        return (
            "file fail" in message
            or "不存在" in message
            or "no such file" in message
            or "not exist" in message
            or "cannot access" in message
        )

    @staticmethod
    def _is_wakeup_failed_message(message: str) -> bool:
        message = (message or "").strip().lower()
        return (
            "device wakeup timed out" in message
            or "wakeup helper timed out" in message
            or "wakeup helper failed" in message
            or "唤醒失败" in message
            or "轮唤醒失败" in message
        )

    @classmethod
    def _normalize_error_detail(cls, message: str) -> str:
        message = str(message or "").strip()
        if cls._is_wakeup_failed_message(message):
            return "唤醒失败"
        return message

    @classmethod
    def _map_failure_status(cls, message: str) -> str:
        if cls._is_device_offline_message(message):
            return "设备离线"
        if cls._is_wakeup_failed_message(message):
            return "唤醒失败"
        return "失败"

    @staticmethod
    def _map_connect_status(message: str) -> str:
        message = (message or "").strip()
        if not message:
            return "连接设备中"
        if "不在线" in message or "设备离线" in message:
            return "设备离线"
        if BatchLogFetchThread._is_wakeup_failed_message(message):
            return "唤醒失败"
        if "检查设备状态" in message:
            return "检查状态中"
        if "唤醒" in message:
            return "唤醒设备中"
        return "连接设备中"

    def _on_connect_status(self, sn, text, connect_details, success_count, failed_count, file_entries):
        detail_text = self._normalize_error_detail(text or "正在登录设备")
        if self._is_wakeup_failed_message(detail_text):
            connect_details[:] = ["唤醒失败"]
        elif self._is_device_offline_message(detail_text):
            connect_details[:] = ["设备离线"]
        else:
            self._append_unique_detail(connect_details, detail_text)
        self._emit_device(
            sn,
            self._map_connect_status(detail_text),
            success_count,
            failed_count,
            file_entries,
            "\n".join(connect_details),
        )

    @staticmethod
    def _append_unique_detail(detail_lines, text):
        for line in str(text or "").splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if normalized not in detail_lines:
                detail_lines.append(normalized)


@register_page("命令", order=3, icon=":/icons/system/cmd.png")
class LogPage(BasePage):
    """日志批量拉取页面。"""

    MAX_WORKERS = 20
    RESULT_HEADERS = ("SN", "状态", "文件", "详情")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "命令"
        self.download_root = self._default_download_root()
        self._row_map = {}
        self.worker_thread = None
        self.fetch_running = False
        self.fetch_canceling = False
        self._commands_updating = False
        self.command_editing = False
        self.init_ui()
        self.load_config()

    def init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)

        self.query_group = QGroupBox("命令执行")
        self.query_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        query_layout = QVBoxLayout(self.query_group)
        query_layout.setContentsMargins(10, 4, 10, 10)
        query_layout.setSpacing(8)

        input_row_frame = QFrame()
        input_row_frame.setFrameShape(QFrame.NoFrame)
        input_row_frame.setStyleSheet("QFrame { border: none; background: transparent; }")
        input_row_layout = QHBoxLayout(input_row_frame)
        input_row_layout.setContentsMargins(0, 0, 0, 0)
        input_row_layout.setSpacing(10)

        self.sn_panel = QFrame()
        self.sn_panel.setFrameShape(QFrame.NoFrame)
        self.sn_panel.setStyleSheet(self._get_borderless_panel_stylesheet())
        sn_panel_layout = QVBoxLayout(self.sn_panel)
        sn_panel_layout.setContentsMargins(0, 0, 0, 0)
        sn_panel_layout.setSpacing(6)
        sn_panel_layout.addWidget(QLabel("SN列表:"))
        self.sn_input = PlainTextEdit()
        self.sn_input.setPlaceholderText("一行一个SN")
        self.sn_input.setFixedHeight(108)
        self.sn_input.setStyleSheet(self._get_text_edit_stylesheet())
        self.sn_input.textChanged.connect(self.save_config)
        sn_panel_layout.addWidget(self.sn_input, 1)

        self.command_panel = QFrame()
        self.command_panel.setFrameShape(QFrame.NoFrame)
        self.command_panel.setStyleSheet(self._get_borderless_panel_stylesheet())
        command_panel_layout = QVBoxLayout(self.command_panel)
        command_panel_layout.setContentsMargins(0, 0, 0, 0)
        command_panel_layout.setSpacing(6)
        command_header_layout = QHBoxLayout()
        command_header_layout.setContentsMargins(0, 0, 0, 0)
        command_header_layout.setSpacing(8)
        command_header_layout.addWidget(QLabel("命令执行列表:"))
        command_header_layout.addStretch()
        self.command_edit_btn = QPushButton("")
        self.command_edit_btn.setFixedHeight(28)
        self.command_edit_btn.setFixedWidth(32)
        self.command_edit_btn.setIconSize(QSize(16, 16))
        self.command_edit_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.command_edit_btn.clicked.connect(self.on_command_edit_button_clicked)
        command_header_layout.addWidget(self.command_edit_btn)
        command_panel_layout.addLayout(command_header_layout)
        self.command_input = CommandPlainTextEdit()
        self.command_input.setPlaceholderText("一行一条命令")
        self.command_input.setFixedHeight(108)
        self.command_input.setStyleSheet(self._get_text_edit_stylesheet())
        self.command_input.textChanged.connect(self.save_config)
        self.command_input.focus_lost.connect(self.on_command_input_focus_lost)
        command_panel_layout.addWidget(self.command_input, 1)

        input_row_layout.addWidget(self.sn_panel, 1)
        input_row_layout.addWidget(self.command_panel, 1)
        query_layout.addWidget(input_row_frame)

        self.bottom_frame = QFrame()
        self.bottom_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        bottom_layout = QHBoxLayout(self.bottom_frame)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(8)

        download_label = QLabel("保存位置:")
        download_label.setFixedWidth(64)
        self.download_path_label = PathDisplayLabel()
        self.download_path_label.setMinimumHeight(28)
        self.download_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.download_path_label.double_clicked.connect(self.open_download_directory)
        self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())

        self.choose_download_path_btn = QPushButton("")
        self.choose_download_path_btn.setIcon(QIcon(":/icons/common/dir.png"))
        self.choose_download_path_btn.setIconSize(QSize(16, 16))
        self.choose_download_path_btn.setFixedSize(32, 28)
        self.choose_download_path_btn.setToolTip("选择保存目录")
        self.choose_download_path_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.choose_download_path_btn.clicked.connect(self.choose_download_directory)

        self.fetch_btn = QPushButton("")
        self.fetch_btn.setIcon(QIcon(":/icons/common/run.png"))
        self.fetch_btn.setIconSize(QSize(16, 16))
        self.fetch_btn.setFixedSize(36, 28)
        self.fetch_btn.setToolTip("执行命令")
        self.fetch_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.fetch_btn.clicked.connect(self.on_fetch_clicked)

        bottom_layout.addWidget(download_label)
        bottom_layout.addWidget(self.download_path_label, 1)
        bottom_layout.addWidget(self.choose_download_path_btn)
        bottom_layout.addSpacing(8)
        bottom_layout.addWidget(self.fetch_btn)
        query_layout.addWidget(self.bottom_frame)

        self.result_group = QGroupBox("执行结果")
        self.result_group.setStyleSheet(StyleManager.get_GROUP_BOX())
        result_layout = QVBoxLayout(self.result_group)
        result_layout.setContentsMargins(10, 15, 10, 10)
        result_layout.setSpacing(3)

        self.summary_label = QLabel("等待开始")
        self.summary_label.setContentsMargins(0, 0, 0, 0)
        self.summary_label.setStyleSheet("margin: 0px; padding: 0px; border: none;")
        result_layout.addWidget(self.summary_label)

        self.result_table = QTableWidget(0, len(self.RESULT_HEADERS))
        self.result_table.setHorizontalHeaderLabels(list(self.RESULT_HEADERS))
        self.result_table.verticalHeader().setVisible(True)
        self.result_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.result_table.verticalHeader().setDefaultSectionSize(self.result_table.verticalHeader().defaultSectionSize())
        self.result_table.verticalHeader().setFixedWidth(36)
        self.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_table.setWordWrap(True)
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.result_table.setItemDelegateForColumn(2, RichTextItemDelegate(self.result_table))
        self.result_table.setItemDelegateForColumn(3, RichTextItemDelegate(self.result_table))
        self.result_table.itemDoubleClicked.connect(self.on_result_item_double_clicked)
        StyleManager.apply_to_widget(self.result_table, "TABLE")
        result_layout.addWidget(self.result_table, 1)

        page_layout.addWidget(self.query_group, 0)
        page_layout.addWidget(self.result_group, 1)

    def load_config(self):
        app_config = config_manager.load_app_config()
        self.sn_input.setPlainText(app_config.last_log_sn or "")
        self.download_root = self._normalize_download_root(app_config.log_download_path)
        self.update_download_path_label()
        self.command_input.setPlainText("\n".join(app_config.log_commands or []))
        self.set_command_editing(False)

    def save_config(self):
        app_config = config_manager.load_app_config()
        app_config.last_log_sn = self.sn_input.toPlainText().strip()
        app_config.log_download_path = self.download_root
        app_config.log_commands = self.get_command_list()[:50]
        config_manager.save_app_config(app_config)

    def on_page_show(self):
        self.show_info("命令页面")
        QTimer.singleShot(0, self._apply_result_column_widths)

    def on_command_edit_button_clicked(self):
        if self.command_editing:
            self.finish_command_editing()
            return
        self.set_command_editing(True)
        self.command_input.setFocus(Qt.OtherFocusReason)

    def on_command_input_focus_lost(self):
        if self.command_edit_btn.hasFocus():
            return
        if self.command_editing:
            self.finish_command_editing()

    def finish_command_editing(self):
        self.save_config()
        self.set_command_editing(False)

    def get_command_list(self):
        commands = []
        for line in self.command_input.toPlainText().splitlines():
            text = line.strip()
            if text:
                commands.append(text)
        return commands

    def on_fetch_clicked(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            if not self.fetch_canceling:
                self.fetch_canceling = True
                self._update_fetch_button_state()
                self.summary_label.setText("正在停止执行...")
                self.show_info("正在停止执行...")
                self.worker_thread.cancel()
            return

        sn_list = self._parse_sn_input(self.sn_input.toPlainText())
        if not sn_list:
            self.show_warning("请输入至少一个设备SN")
            return

        commands = self.get_command_list()
        if not commands:
            self.show_warning("请至少配置一条拉日志命令")
            return

        env, device_username, device_password = get_account_config()
        if not device_username or not device_password:
            self.show_warning("请先在设置中配置运维账号")
            return

        seetong_username, seetong_password = get_seetong_account_config()
        seetong_username = (seetong_username or "").strip()
        seetong_password = (seetong_password or "").strip()
        if not seetong_username or not seetong_password:
            prompt_configure_account(
                self,
                "需要配置Seetong账号",
                "检测到Seetong账号未配置，是否现在配置？",
                initial_tab=0,
            )
            return

        self.save_config()
        self._prepare_result_table(sn_list)
        self._set_running_state(True)
        self.summary_label.setText(f"正在批量拉取日志，共 {len(sn_list)} 台设备，线程数 {self.MAX_WORKERS}")
        self.show_progress(self.summary_label.text())

        self.worker_thread = BatchLogFetchThread(
            sn_list=sn_list,
            commands=commands,
            download_root=self.download_root,
            env=env,
            device_username=device_username,
            device_password=device_password,
            seetong_username=seetong_username,
            seetong_password=seetong_password,
            max_workers=self.MAX_WORKERS,
        )
        self.worker_thread.device_updated.connect(self.on_device_updated)
        self.worker_thread.summary_ready.connect(self.on_summary_ready)
        self.worker_thread.error_signal.connect(self.on_worker_error)
        self.worker_thread.finished.connect(self.on_worker_finished)
        self.fetch_running = True
        self.fetch_canceling = False
        self._update_fetch_button_state()
        self.worker_thread.start()
        self.fetch_btn.repaint()

    def on_device_updated(self, payload: dict):
        sn = payload.get("sn", "")
        row = self._row_map.get(sn)
        if row is None:
            return

        status_text = str(payload.get("status") or "")
        file_text = "\n".join(payload.get("files") or [])
        detail_text = str(payload.get("detail") or "")
        self.result_table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
        values = [sn, status_text, file_text, detail_text]

        for column, value in enumerate(values):
            item = self.result_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                self.result_table.setItem(row, column, item)
            item.setText(value)
            item.setToolTip(value)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            self._apply_item_color(item, column, value)

        file_item = self.result_table.item(row, 2)
        detail_item = self.result_table.item(row, 3)
        if file_item is not None:
            file_item.setData(RICH_TEXT_ROLE, self._build_file_segments(payload.get("files") or []))
        if detail_item is not None:
            detail_item.setData(RICH_TEXT_ROLE, self._build_detail_segments(detail_text))
        self.result_table.resizeRowToContents(row)

    def on_result_item_double_clicked(self, item):
        if item is None:
            return
        text = item.text() or ""
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self.show_success("已复制单元格内容", 1200)

    def on_summary_ready(self, summary: dict):
        if summary.get("cancelled"):
            message = (
                f"执行已取消：共 {summary.get('total', 0)} 台，"
                f"已完成 {int(summary.get('success_devices', 0)) + int(summary.get('partial_devices', 0))} 台，"
                f"下载文件 {summary.get('total_files', 0)} 个，"
                f"耗时 {self._format_duration(summary.get('duration_seconds', 0.0))}"
            )
            self.summary_label.setText(message)
            self.show_warning(message, 5000)
            return
        completed_devices = int(summary.get("success_devices", 0)) + int(summary.get("partial_devices", 0))
        failed_devices = int(summary.get("total", 0)) - completed_devices
        message = (
            f"执行完成：共 {summary.get('total', 0)} 台，"
            f"完成 {completed_devices} 台，"
            f"失败 {failed_devices} 台，"
            f"下载文件 {summary.get('total_files', 0)} 个，"
            f"耗时 {self._format_duration(summary.get('duration_seconds', 0.0))}"
        )
        self.summary_label.setText(message)
        self.show_success(message, 5000)

    def on_worker_error(self, message: str):
        self.show_error(message)

    def on_worker_finished(self):
        self.fetch_running = False
        self.fetch_canceling = False
        self._set_running_state(False)
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None
        self._apply_result_column_widths()

    def choose_download_directory(self):
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "选择日志下载目录",
            self.download_root,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not selected_dir:
            return
        self.download_root = self._normalize_download_root(selected_dir)
        self.update_download_path_label()
        self.save_config()

    def open_download_directory(self):
        directory = Path(self.download_root)
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def update_download_path_label(self):
        self.download_path_label.setText(self.download_root)
        self.download_path_label.setToolTip(f"{self.download_root}\n双击打开目录")

    def cleanup(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            self.fetch_running = False
            self.fetch_canceling = False
            self.worker_thread.cancel()
            self.worker_thread.wait(3000)

    def _prepare_result_table(self, sn_list):
        self._row_map = {}
        self.result_table.setRowCount(0)
        for row, sn in enumerate(sn_list):
            self.result_table.insertRow(row)
            self._row_map[sn] = row
            self.result_table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
            initial_values = [sn, "等待执行", "", ""]
            for column, value in enumerate(initial_values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                self._apply_item_color(item, column, value)
                if column in (2, 3):
                    item.setData(RICH_TEXT_ROLE, [])
                self.result_table.setItem(row, column, item)
        self._apply_result_column_widths()

    def _set_running_state(self, running: bool):
        self.fetch_btn.setEnabled(True)
        self.choose_download_path_btn.setEnabled(not running)
        self.command_edit_btn.setEnabled(not running)
        self.command_input.setEnabled(not running)
        self.sn_input.setEnabled(not running)
        self._update_fetch_button_state()
        if running:
            self.command_input.setReadOnly(True)
        else:
            self.command_input.setReadOnly(not self.command_editing)

    def set_command_editing(self, editing: bool):
        self.command_editing = bool(editing)
        self.command_input.setReadOnly(not self.command_editing)
        self.command_edit_btn.setText("")
        self.command_edit_btn.setIcon(QIcon(":/icons/common/save.png") if self.command_editing else QIcon(":/icons/common/edit.png"))
        self.command_edit_btn.setToolTip("保存命令列表" if self.command_editing else "编辑命令列表")

    def _update_fetch_button_state(self):
        if self.fetch_running:
            self.fetch_btn.setIcon(QIcon(":/icons/common/connectting.png"))
            self.fetch_btn.setToolTip("停止中..." if self.fetch_canceling else "停止执行")
        else:
            self.fetch_btn.setIcon(QIcon(":/icons/common/run.png"))
            self.fetch_btn.setToolTip("执行命令")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_result_column_widths()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_result_column_widths)

    def refresh_theme(self):
        if hasattr(self, "query_group"):
            self.query_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        if hasattr(self, "result_group"):
            self.result_group.setStyleSheet(StyleManager.get_GROUP_BOX())
        if hasattr(self, "sn_panel"):
            self.sn_panel.setStyleSheet(self._get_borderless_panel_stylesheet())
        if hasattr(self, "command_panel"):
            self.command_panel.setStyleSheet(self._get_borderless_panel_stylesheet())
        if hasattr(self, "bottom_frame"):
            self.bottom_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        if hasattr(self, "sn_input"):
            self.sn_input.setStyleSheet(self._get_text_edit_stylesheet())
        if hasattr(self, "command_input"):
            self.command_input.setStyleSheet(self._get_text_edit_stylesheet())
        if hasattr(self, "command_edit_btn"):
            self.command_edit_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        if hasattr(self, "choose_download_path_btn"):
            self.choose_download_path_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        if hasattr(self, "fetch_btn"):
            self.fetch_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        if hasattr(self, "download_path_label"):
            self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())
        if hasattr(self, "result_table"):
            StyleManager.apply_to_widget(self.result_table, "TABLE")
            for row in range(self.result_table.rowCount()):
                for column in range(self.result_table.columnCount()):
                    item = self.result_table.item(row, column)
                    if item is None:
                        continue
                    self._apply_item_color(item, column, item.text())
                    if column == 2:
                        item.setData(RICH_TEXT_ROLE, self._build_file_segments(item.text().splitlines()))
                    elif column == 3:
                        item.setData(RICH_TEXT_ROLE, self._build_detail_segments(item.text()))
            self.result_table.viewport().update()

    @staticmethod
    def _parse_sn_input(text: str):
        tokens = re.split(r"[\s,，;；]+", text or "")
        seen = set()
        sn_list = []
        for token in tokens:
            sn = token.strip()
            if not sn or sn in seen:
                continue
            seen.add(sn)
            sn_list.append(sn)
        return sn_list

    @staticmethod
    def _default_download_root() -> str:
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            return str(desktop)
        return str(Path.home())

    def _normalize_download_root(self, path: str) -> str:
        path = (path or "").strip()
        if not path:
            return self._default_download_root()
        return str(Path(path).expanduser())

    @staticmethod
    def _get_download_path_label_stylesheet():
        return f"""
        QLabel {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px 6px;
        }}
        QLabel:hover {{
            border: 1px solid {t('border_hover')};
        }}
        """

    @staticmethod
    def _get_text_edit_stylesheet():
        return StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit")

    @staticmethod
    def _get_borderless_panel_stylesheet():
        return "QFrame { border: none; background: transparent; }"

    @staticmethod
    def _get_compact_group_box_stylesheet():
        return f"""
        QGroupBox {{
            color: {t('text_primary')};
            font-size: 12px;
            font-weight: bold;
            border: 1px solid {t('border')};
            border-radius: 4px;
            margin-top: 8px;
            margin-bottom: 8px;
            padding-top: 6px;
            background-color: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }}
        """

    @staticmethod
    def _format_duration(duration_seconds) -> str:
        try:
            total_seconds = max(0, int(round(float(duration_seconds or 0))))
        except (TypeError, ValueError):
            total_seconds = 0
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _apply_result_column_widths(self):
        if not hasattr(self, "result_table"):
            return

        viewport_width = self.result_table.viewport().width()
        if viewport_width <= 0:
            return

        total_ratio = 2 + 1 + 2 + 6
        unit = max(1, viewport_width // total_ratio)
        sn_width = max(140, unit * 2)
        status_width = max(90, unit * 1)
        file_width = max(160, unit * 2)
        detail_width = max(260, viewport_width - sn_width - status_width - file_width)
        self.result_table.setColumnWidth(0, sn_width)
        self.result_table.setColumnWidth(1, status_width)
        self.result_table.setColumnWidth(2, file_width)
        self.result_table.setColumnWidth(3, detail_width)
        self.result_table.resizeRowsToContents()

    @staticmethod
    def _status_color(status: str) -> str:
        status = (status or "").strip()
        if status in ("完成", "部分完成"):
            return t("status_online")
        if status in ("失败", "设备离线", "唤醒失败"):
            return t("status_offline")
        return t("text_primary")

    @staticmethod
    def _file_line_color(line: str) -> str:
        text = (line or "").strip()
        if not text:
            return t("text_primary")
        if "不存在" in text:
            return t("status_pending")
        if "获取失败" in text or text.endswith("失败"):
            return t("status_offline")
        return t("status_online")

    @staticmethod
    def _detail_line_color(line: str) -> str:
        text = (line or "").strip()
        if not text:
            return t("text_primary")
        if any(keyword in text for keyword in ("执行失败", "获取失败", "设备离线", "唤醒失败", "失败", "不存在")):
            return t("status_offline")
        if any(keyword in text for keyword in ("成功", "已执行")):
            return t("status_online")
        return t("text_primary")

    def _apply_item_color(self, item: QTableWidgetItem, column: int, value: str):
        if column == 1:
            item.setForeground(self._create_brush(self._status_color(value)))
            return
        item.setForeground(self._create_brush(t("text_primary")))

    def _build_file_segments(self, lines):
        return [
            {"text": str(line), "color": self._file_line_color(str(line))}
            for line in lines
            if str(line).strip()
        ]

    def _build_detail_segments(self, detail_text: str):
        return [
            {"text": line, "color": self._detail_line_color(line)}
            for line in str(detail_text or "").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _create_brush(color: str):
        from PyQt5.QtGui import QBrush, QColor

        return QBrush(QColor(color))
