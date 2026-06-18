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
from PyQt5.QtGui import QDesktopServices, QFontMetrics, QIcon, QTextDocument
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QAction,
    QMenu,
    QSizePolicy,
    QStyledItemDelegate,
    QStyle,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.ui import (
    Action,
    BodyLabel,
    CheckBox,
    ElevatedCardWidget,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    RoundMenu,
    StrongBodyLabel,
    TableWidget,
    TextEdit,
)
from query_tool.utils import StyleManager, config_manager, get_account_config, get_seetong_account_config
from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.logger import logger
from query_tool.utils.siot_debug import DEFAULT_COMMAND_TIMEOUT_MS, is_getsystemcfg_command, is_syscmd_family_command
from query_tool.utils.siot_debug.service import resolve_device_credentials
from query_tool.utils.theme_manager import t


ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
RICH_TEXT_ROLE = Qt.UserRole + 1


class PathDisplayLabel(BodyLabel):
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
            lines.append(
                f'<div style="color: {color}; white-space: pre-wrap; '
                f'overflow-wrap: anywhere; word-break: break-word;">{text}</div>'
            )
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
                    total_files += int(result.get("downloaded_file_count") or 0)
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
                "downloaded_file_count": 0,
                "total_commands": 0,
                "files": [],
                "detail": "已取消",
            }
        success_count = 0
        failed_count = 0
        downloaded_file_count = 0
        file_entries = []
        details = []
        connect_details = []
        connected_ok = False
        commands = [self._normalize_command(raw) for raw in self.commands]
        commands = [command for command in commands if command]
        total_commands = len(commands)

        self._emit_device(
            sn,
            "查询设备密码中",
            success_count,
            failed_count,
            file_entries,
            "正在获取设备密码",
            total_commands=total_commands,
            downloaded_file_count=downloaded_file_count,
        )
        try:
            credentials, _ = resolve_device_credentials(
                sn,
                self.env,
                self.device_username,
                self.device_password,
            )
        except Exception as exc:
            if self._stop_event.is_set():
                return self._build_cancelled_result(
                    sn,
                    success_count,
                    failed_count,
                    downloaded_file_count,
                    file_entries,
                )
            normalized_message = self._normalize_error_detail(str(exc))
            detail_message = "设备离线" if self._is_device_offline_message(normalized_message) else normalized_message
            status_text = self._map_failure_status(normalized_message)
            self._emit_device(
                sn,
                status_text,
                success_count,
                failed_count + 1,
                file_entries,
                detail_message,
                total_commands=total_commands,
                downloaded_file_count=downloaded_file_count,
            )
            return {
                "sn": sn,
                "status": status_text,
                "success_count": success_count,
                "failed_count": failed_count + 1,
                "downloaded_file_count": downloaded_file_count,
                "total_commands": total_commands,
                "files": file_entries,
                "detail": detail_message,
            }

        if self._stop_event.is_set():
            self._emit_device(
                sn,
                "已取消",
                success_count,
                failed_count,
                file_entries,
                "已取消",
                total_commands=total_commands,
                downloaded_file_count=downloaded_file_count,
            )
            return {
                "sn": sn,
                "status": "已取消",
                "success_count": success_count,
                "failed_count": failed_count,
                "downloaded_file_count": downloaded_file_count,
                "total_commands": total_commands,
                "files": file_entries,
                "detail": "已取消",
            }

        self._emit_device(
            sn,
            "连接设备中",
            success_count,
            failed_count,
            file_entries,
            "正在登录设备",
            total_commands=total_commands,
            downloaded_file_count=downloaded_file_count,
        )
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

            for index, command in enumerate(commands, 1):
                if self._stop_event.is_set():
                    break

                self._emit_device(
                    sn,
                    f"执行中 {index}/{total_commands}",
                    success_count,
                    failed_count,
                    file_entries,
                    f"执行命令: {command}",
                    total_commands=total_commands,
                    current_command_index=index,
                    current_command=command,
                    downloaded_file_count=downloaded_file_count,
                )

                try:
                    command_result = self._run_command(process, event_queue, command)
                    if is_getsystemcfg_command(command):
                        if command_result.get("saved_file"):
                            file_entries.append(command_result["saved_file"])
                            success_count += 1
                            downloaded_file_count += 1
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
                            success_count += 1
                            details.append(f"{command}: {command_result.get('message') or '已执行'}")
                        else:
                            failed_count += 1
                            details.append(f"{command}: {command_result.get('message') or '执行失败'}")
                except Exception as exc:
                    failed_count += 1
                    details.append(f"{command}: {exc}")

                self._emit_device(
                    sn,
                    f"执行中 {index}/{total_commands}",
                    success_count,
                    failed_count,
                    file_entries,
                    "\n".join(details),
                    total_commands=total_commands,
                    current_command_index=index,
                    current_command=command,
                    downloaded_file_count=downloaded_file_count,
                )
        except Exception as exc:
            if self._stop_event.is_set():
                return self._build_cancelled_result(
                    sn,
                    success_count,
                    failed_count,
                    downloaded_file_count,
                    file_entries,
                )
            normalized_message = self._normalize_error_detail(str(exc))
            detail_message = "设备离线" if self._is_device_offline_message(normalized_message) else normalized_message
            status_text = self._map_failure_status(normalized_message)
            if status_text in ("唤醒失败", "设备离线"):
                detail_lines = [detail_message]
            else:
                detail_lines = list(connect_details)
                self._append_unique_detail(detail_lines, detail_message)
            self._emit_device(
                sn,
                status_text,
                success_count,
                failed_count + 1,
                file_entries,
                "\n".join(detail_lines),
                total_commands=total_commands,
                downloaded_file_count=downloaded_file_count,
            )
            return {
                "sn": sn,
                "status": status_text,
                "success_count": success_count,
                "failed_count": failed_count + 1,
                "downloaded_file_count": downloaded_file_count,
                "total_commands": total_commands,
                "files": file_entries,
                "detail": "\n".join(detail_lines),
            }
        finally:
            if process is not None:
                try:
                    if connected_ok:
                        self._emit_device(
                            sn,
                            "正在注销",
                            success_count,
                            failed_count,
                            file_entries,
                            "\n".join(details) or "正在断开设备连接",
                            total_commands=total_commands,
                            downloaded_file_count=downloaded_file_count,
                        )
                        self._disconnect_process(process, event_queue)
                finally:
                    self._close_process(process)
                    time.sleep(0.05)

        if self._stop_event.is_set():
            return self._build_cancelled_result(
                sn,
                success_count,
                failed_count,
                downloaded_file_count,
                file_entries,
            )

        if success_count > 0 and failed_count == 0:
            final_status = "完成"
        elif success_count > 0:
            final_status = "部分完成"
        else:
            final_status = "失败"

        final_detail = "\n".join(details) if details else "执行完成"
        self._emit_device(
            sn,
            final_status,
            success_count,
            failed_count,
            file_entries,
            final_detail,
            total_commands=total_commands,
            downloaded_file_count=downloaded_file_count,
        )
        return {
            "sn": sn,
            "status": final_status,
            "success_count": success_count,
            "failed_count": failed_count,
            "downloaded_file_count": downloaded_file_count,
            "total_commands": total_commands,
            "files": file_entries,
            "detail": final_detail,
        }

    def _emit_device(self, sn, status, success_count, failed_count, files, detail, **extra):
        payload = {
            "sn": sn,
            "status": status,
            "success_count": success_count,
            "failed_count": failed_count,
            "files": list(files),
            "detail": detail,
        }
        payload.update(extra)
        self.device_updated.emit(payload)

    def _build_cancelled_result(self, sn, success_count, failed_count, downloaded_file_count, files):
        self._emit_device(sn, "已取消", success_count, failed_count, files, "已取消")
        return {
            "sn": sn,
            "status": "已取消",
            "success_count": success_count,
            "failed_count": failed_count,
            "downloaded_file_count": downloaded_file_count,
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
                    "dev_id": credentials.dev_id,
                    "protocol": credentials.protocol,
                    "is_siot": credentials.is_siot,
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
    def _can_send_payload(process) -> bool:
        if process is None:
            return False
        try:
            if process.poll() is not None:
                return False
        except Exception:
            return False
        stdin = getattr(process, "stdin", None)
        return stdin is not None and not getattr(stdin, "closed", False)

    def _disconnect_process(self, process, event_queue):
        if not self._can_send_payload(process):
            return
        try:
            self._send_payload(process, {"action": "disconnect"})
        except (BrokenPipeError, OSError, ValueError) as exc:
            logger.debug(f"日志设备子进程已提前关闭，跳过断开指令: {exc}")
            return
        try:
            self._drain_until_disconnected(event_queue, timeout_s=2.5)
        except RuntimeError as exc:
            logger.debug(f"等待日志设备子进程断开超时，继续关闭进程: {exc}")

    @staticmethod
    def _send_payload(process, payload: dict):
        if process is None:
            raise RuntimeError("日志子进程未启动")
        stdin = getattr(process, "stdin", None)
        if stdin is None:
            raise RuntimeError("日志子进程未启动")
        if getattr(stdin, "closed", False):
            raise BrokenPipeError("日志子进程输入流已关闭")
        try:
            if process.poll() is not None:
                raise BrokenPipeError("日志子进程已退出")
        except BrokenPipeError:
            raise
        except Exception:
            pass
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            stdin.write(data)
            stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise BrokenPipeError("日志子进程通信已断开") from exc

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
    MAX_COMMANDS = 50
    RESULT_ROW_HEIGHT = 34
    RESULT_HEADERS = ("选择", "SN", "状态", "概览")
    RESULT_MIN_WIDTHS = {0: 56, 1: 170, 2: 110, 3: 220}
    DEFAULT_LOG_COMMANDS = [
        "GetSystemCfg /mnt/nand/keylog.data",
        "GetSystemCfg /mnt/nand/dmsg1.txt",
        "GetSystemCfg /mnt/nand/dmsg3.txt",
        "GetSystemCfg /mnt/nand/dmsg4.txt",
        "GetSystemCfg /tmp/sd_room/IPC_Log/Tps_RecordLogNew.log",
        "GetSystemCfg /tmp/sd_room/IPC_Log/panic.log",
        "GetSystemCfg /tmp/sd_room/dmesg0.log",
        "GetSystemCfg /tmp/sd_room/dmesg1.log",
        "GetSystemCfg /tmp/sd_room/4gErrLog",
        "GetSystemCfg /tmp/sd_room/test_sysinfo.txt",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "命令"
        self._cards = []
        self._card_title_labels = []
        self.download_root = self._default_download_root()
        self._row_map = {}
        self._device_payloads = {}
        self.worker_thread = None
        self.fetch_running = False
        self.fetch_canceling = False
        self._config_loading = False
        self._commands_updating = False
        self.command_editing = False
        self._resizing_columns = False
        self._result_checkbox_updating = False
        self._current_run_mode = "execute"
        self.init_ui()
        self.load_config()

    def _apply_card_title_style(self, label):
        label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")

    def _apply_card_style(self, card):
        if not QFLUENT_WIDGETS_AVAILABLE:
            card.setStyleSheet(
                f"""
                #{card.objectName()} {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )

    def _create_card_section(self, title, vertical_policy=QSizePolicy.Fixed):
        card = ElevatedCardWidget(self)
        card.setObjectName(f"logPageCard{len(self._cards) + 1}")
        self._cards.append(card)
        card.setSizePolicy(QSizePolicy.Expanding, vertical_policy)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title_label = StrongBodyLabel(title)
        self._card_title_labels.append(title_label)
        self._apply_card_title_style(title_label)
        layout.addWidget(title_label)
        self._apply_card_style(card)
        return card, layout

    def _create_subsection_card(self, title, vertical_policy=QSizePolicy.Expanding):
        card = ElevatedCardWidget(self)
        card.setObjectName(f"logSubCard{len(self._cards) + 1}")
        self._cards.append(card)
        card.setSizePolicy(QSizePolicy.Expanding, vertical_policy)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = BodyLabel(title)
        self._card_title_labels.append(title_label)
        self._apply_card_title_style(title_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        self._apply_card_style(card)
        return card, layout, header_layout

    def _apply_plain_text_edit_style(self, widget):
        if not QFLUENT_WIDGETS_AVAILABLE:
            widget.setStyleSheet(self._get_plain_text_edit_stylesheet())

    def _apply_rich_text_edit_style(self, widget):
        if not QFLUENT_WIDGETS_AVAILABLE:
            widget.setStyleSheet(self._get_rich_text_edit_stylesheet())

    def _apply_table_style(self):
        if hasattr(self, "result_table") and not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.result_table, "TABLE")

    def _control_height(self, extra_padding: int = 12, minimum: int = 32) -> int:
        metrics = QFontMetrics(self.font())
        return max(minimum, metrics.height() + extra_padding)

    def _create_menu_action(self, text, handler):
        if QFLUENT_WIDGETS_AVAILABLE and Action is not None:
            action = Action(text, self)
        else:
            action = QAction(text, self)
        action.triggered.connect(handler)
        return action

    def _show_menu(self, menu, global_pos):
        exec_method = getattr(menu, "exec", None)
        if callable(exec_method):
            exec_method(global_pos)
            return
        exec_method = getattr(menu, "exec_", None)
        if callable(exec_method):
            exec_method(global_pos)

    def init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)
        control_height = self._control_height()
        toolbar_height = max(38, control_height + 6)

        self.query_group, query_layout = self._create_card_section("命令执行")
        query_layout.setSpacing(12)

        input_row_layout = QHBoxLayout()
        input_row_layout.setContentsMargins(0, 0, 0, 0)
        input_row_layout.setSpacing(10)

        self.sn_panel, sn_panel_layout, _sn_header_layout = self._create_subsection_card("SN 列表")
        self.sn_input = PlainTextEdit()
        self.sn_input.setPlaceholderText("一行一个SN")
        self.sn_input.setFixedHeight(108)
        self._apply_plain_text_edit_style(self.sn_input)
        self.sn_input.textChanged.connect(self.save_config)
        sn_panel_layout.addWidget(self.sn_input, 1)

        self.command_panel, command_panel_layout, command_header_layout = self._create_subsection_card("命令执行列表")
        self.command_edit_btn = PushButton("")
        self.command_edit_btn.setFixedHeight(control_height)
        self.command_edit_btn.setFixedWidth(control_height)
        self.command_edit_btn.setIconSize(QSize(16, 16))
        self.command_edit_btn.clicked.connect(self.on_command_edit_button_clicked)
        command_header_layout.addWidget(self.command_edit_btn)
        self.command_input = CommandPlainTextEdit()
        self.command_input.setPlaceholderText("一行一条命令")
        self.command_input.setFixedHeight(108)
        self._apply_plain_text_edit_style(self.command_input)
        self.command_input.textChanged.connect(self.save_config)
        self.command_input.focus_lost.connect(self.on_command_input_focus_lost)
        self.command_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.command_input.customContextMenuRequested.connect(self.on_command_input_context_menu)
        command_panel_layout.addWidget(self.command_input, 1)

        input_row_layout.addWidget(self.sn_panel, 1)
        input_row_layout.addWidget(self.command_panel, 1)
        query_layout.addLayout(input_row_layout)

        self.bottom_frame = QWidget()
        self._apply_plain_toolbar_style(self.bottom_frame)
        self.bottom_frame.setFixedHeight(toolbar_height)
        bottom_layout = QHBoxLayout(self.bottom_frame)
        bottom_layout.setContentsMargins(2, 2, 2, 2)
        bottom_layout.setSpacing(6)

        download_label = BodyLabel("保存位置:")
        download_label.setFixedWidth(64)
        download_label.setFixedHeight(control_height)
        download_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.download_path_label = PathDisplayLabel()
        self.download_path_label.setFixedHeight(control_height)
        self.download_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.download_path_label.double_clicked.connect(self.open_download_directory)
        self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())

        self.choose_download_path_btn = PushButton("")
        self.choose_download_path_btn.setIcon(QIcon(":/icons/common/dir.png"))
        self.choose_download_path_btn.setIconSize(QSize(16, 16))
        self.choose_download_path_btn.setFixedSize(36, control_height)
        self.choose_download_path_btn.setToolTip("选择保存目录")
        self.choose_download_path_btn.clicked.connect(self.choose_download_directory)

        self.fetch_btn = PrimaryPushButton("发送")
        self.fetch_btn.setIcon(QIcon(":/icons/common/run.png"))
        self.fetch_btn.setIconSize(QSize(16, 16))
        self.fetch_btn.setFixedSize(76, control_height)
        self.fetch_btn.setToolTip("执行命令")
        self.fetch_btn.clicked.connect(self.on_fetch_clicked)

        bottom_layout.addWidget(download_label)
        bottom_layout.addWidget(self.download_path_label, 1)
        bottom_layout.addWidget(self.choose_download_path_btn)
        bottom_layout.addSpacing(6)
        bottom_layout.addWidget(self.fetch_btn)
        query_layout.addWidget(self.bottom_frame)

        self.result_group, result_layout = self._create_card_section("执行结果", QSizePolicy.Expanding)
        result_layout.setSpacing(8)

        self.summary_label = BodyLabel("等待开始")
        self.summary_label.setContentsMargins(0, 0, 0, 0)
        self.summary_label.setStyleSheet("margin: 0px; padding: 0px; border: none;")
        self.summary_label.setVisible(False)
        result_layout.addWidget(self.summary_label)

        self.detail_header_label = BodyLabel("设备执行详情")
        self.detail_header_label.setContentsMargins(0, 0, 0, 0)
        self.detail_header_label.setStyleSheet("margin: 0px; padding: 0px; border: none;")
        self.detail_header_label.setVisible(False)
        result_layout.addWidget(self.detail_header_label)

        self.result_table = TableWidget()
        self.result_table.setRowCount(0)
        self.result_table.setColumnCount(len(self.RESULT_HEADERS))
        self.result_table.setHorizontalHeaderLabels(list(self.RESULT_HEADERS))
        self.result_table.verticalHeader().setVisible(True)
        self.result_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.result_table.verticalHeader().setDefaultSectionSize(self.RESULT_ROW_HEIGHT)
        self.result_table.verticalHeader().setFixedWidth(36)
        self.result_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.result_table.setWordWrap(False)
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.result_table.horizontalHeader().setStretchLastSection(False)
        self.result_table.horizontalHeader().sectionResized.connect(self.on_result_section_resized)
        self.result_table.itemDoubleClicked.connect(self.on_result_item_double_clicked)
        self.result_table.itemSelectionChanged.connect(self.on_result_selection_changed)
        self._overview_delegate = RichTextItemDelegate(self.result_table)
        self.result_table.setItemDelegateForColumn(3, self._overview_delegate)
        self._apply_table_style()

        result_content = QHBoxLayout()
        result_content.setContentsMargins(0, 0, 0, 0)
        result_content.setSpacing(10)

        self.table_panel, table_layout, _table_header_layout = self._create_subsection_card("设备列表")

        table_action_row = QHBoxLayout()
        table_action_row.setContentsMargins(0, 0, 0, 0)
        table_action_row.setSpacing(8)
        self.result_select_all_checkbox = CheckBox("全选")
        self.result_select_all_checkbox.setTristate(False)
        self.result_select_all_checkbox.setEnabled(False)
        self.result_select_all_checkbox.stateChanged.connect(self.on_result_select_all_changed)
        table_action_row.addWidget(self.result_select_all_checkbox)

        self.result_selection_label = BodyLabel("未选择设备")
        self.result_selection_label.setStyleSheet(f"color: {t('text_secondary')}; border: none;")
        table_action_row.addWidget(self.result_selection_label)
        table_action_row.addStretch()

        self.retry_btn = PushButton("重试")
        self.retry_btn.setIcon(QIcon(":/icons/common/run.png"))
        self.retry_btn.setIconSize(QSize(16, 16))
        self.retry_btn.setFixedSize(76, control_height)
        self.retry_btn.setToolTip("重试勾选的失败设备")
        self.retry_btn.setEnabled(False)
        self.retry_btn.clicked.connect(self.on_retry_clicked)
        table_action_row.addWidget(self.retry_btn)

        table_layout.addLayout(table_action_row)
        table_layout.addWidget(self.result_table, 1)

        self.result_corner_checkbox = CheckBox()
        self.result_corner_checkbox.setTristate(False)
        self.result_corner_checkbox.setToolTip("全选/取消全选")
        self.result_corner_checkbox.setEnabled(False)
        self.result_corner_checkbox.stateChanged.connect(self.on_corner_select_all_changed)
        corner_widget = QWidget()
        corner_layout = QHBoxLayout(corner_widget)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.addWidget(self.result_corner_checkbox, 0, Qt.AlignCenter)
        self.result_table.setCornerWidget(corner_widget)

        self.detail_panel, detail_layout, _detail_header_layout = self._create_subsection_card("设备执行详情")

        self.detail_view = TextEdit()
        self.detail_view.setReadOnly(True)
        self.detail_view.setAcceptRichText(True)
        self.detail_view.setMinimumWidth(300)
        self._apply_rich_text_edit_style(self.detail_view)
        self.detail_view.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        detail_layout.addWidget(self.detail_view, 1)

        result_content.addWidget(self.table_panel, 7)
        result_content.addWidget(self.detail_panel, 4)
        result_layout.addLayout(result_content, 1)

        page_layout.addWidget(self.query_group, 0)
        page_layout.addWidget(self.result_group, 1)

    def load_config(self):
        app_config = config_manager.load_app_config()
        command_list, should_save = self._resolve_initial_command_list(app_config)

        self._config_loading = True
        try:
            self.sn_input.setPlainText(app_config.last_log_sn or "")
            self.download_root = self._normalize_download_root(app_config.log_download_path)
            self.update_download_path_label()
            self._set_command_list(command_list)
            self.set_command_editing(False)
        finally:
            self._config_loading = False

        if should_save:
            config_manager.save_app_config(app_config)

    def save_config(self):
        if self._config_loading or self._commands_updating:
            return
        app_config = config_manager.load_app_config()
        app_config.last_log_sn = self.sn_input.toPlainText().strip()
        app_config.log_download_path = self.download_root
        app_config.log_commands = self.get_command_list()[:self.MAX_COMMANDS]
        app_config.log_commands_initialized = True
        config_manager.save_app_config(app_config)

    def on_page_show(self):
        self.show_info("命令页面")
        QTimer.singleShot(0, self._apply_result_column_widths)
        self._restore_current_detail_view()

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

    def on_command_input_context_menu(self, pos):
        global_pos = self.command_input.viewport().mapToGlobal(pos)
        if QFLUENT_WIDGETS_AVAILABLE and RoundMenu is not None:
            menu = RoundMenu(parent=self.command_input)
            has_selection = self.command_input.textCursor().hasSelection()
            can_edit = not self.command_input.isReadOnly()
            actions = [
                ("复制", self.command_input.copy, has_selection),
                ("剪切", self.command_input.cut, has_selection and can_edit),
                ("粘贴", self.command_input.paste, can_edit),
                ("全选", self.command_input.selectAll, bool(self.command_input.toPlainText())),
            ]
            for text, handler, enabled in actions:
                action = self._create_menu_action(text, handler)
                action.setEnabled(enabled)
                menu.addAction(action)

            menu.addSeparator()
            restore_action = self._create_menu_action("恢复默认命令列表", self.on_restore_default_commands_clicked)
            restore_action.setEnabled(not self.fetch_running)
            menu.addAction(restore_action)
            self._show_menu(menu, global_pos)
            return

        menu = self.command_input.createStandardContextMenu()
        menu.setStyleSheet(self._get_context_menu_stylesheet())
        menu.addSeparator()
        restore_action = menu.addAction("恢复默认命令列表")
        restore_action.setEnabled(not self.fetch_running)
        selected_action = menu.exec_(global_pos)
        if selected_action == restore_action:
            self.on_restore_default_commands_clicked()

    def get_command_list(self):
        commands = []
        for line in self.command_input.toPlainText().splitlines():
            text = line.strip()
            if text:
                commands.append(text)
        return commands

    def on_restore_default_commands_clicked(self):
        self._set_command_list(self._default_command_list())
        self.save_config()
        if self.command_editing:
            self.set_command_editing(False)
        self.show_success("已恢复默认命令列表", 1500)

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
        self._start_execution(sn_list, reset_table=True, run_mode="execute")

    def on_retry_clicked(self):
        if self.fetch_running:
            return

        selected_sns = self._get_selected_retryable_sns()
        if not selected_sns:
            self.show_warning("请先勾选至少一台失败设备后再重试")
            return

        self._start_execution(selected_sns, reset_table=False, run_mode="retry")

    def _collect_execution_context(self):
        commands = self.get_command_list()
        if not commands:
            self.show_warning("请至少配置一条拉日志命令")
            return None

        env, device_username, device_password = get_account_config()
        if not device_username or not device_password:
            self.show_warning("请先在设置中配置运维账号")
            return None

        seetong_username, seetong_password = get_seetong_account_config()
        seetong_username = (seetong_username or "").strip()
        seetong_password = (seetong_password or "").strip()
        return {
            "commands": commands,
            "env": env,
            "device_username": device_username,
            "device_password": device_password,
            "seetong_username": seetong_username,
            "seetong_password": seetong_password,
        }

    def _start_execution(self, sn_list, *, reset_table: bool, run_mode: str):
        sn_list = [sn for sn in sn_list if sn]
        if not sn_list:
            self.show_warning("请输入至少一个设备SN")
            return

        context = self._collect_execution_context()
        if not context:
            return

        self.save_config()
        self._current_run_mode = run_mode
        if reset_table:
            self._prepare_result_table(sn_list)
        else:
            self._prepare_retry_rows(sn_list)

        self._set_running_state(True)
        action_text = "正在重试失败设备" if run_mode == "retry" else "正在批量拉取日志"
        self.summary_label.setText(f"{action_text}，共 {len(sn_list)} 台设备，线程数 {self.MAX_WORKERS}")
        self.show_progress(self.summary_label.text())

        self.worker_thread = BatchLogFetchThread(
            sn_list=sn_list,
            commands=context["commands"],
            download_root=self.download_root,
            env=context["env"],
            device_username=context["device_username"],
            device_password=context["device_password"],
            seetong_username=context["seetong_username"],
            seetong_password=context["seetong_password"],
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

        self._device_payloads[sn] = {
            "sn": sn,
            "status": str(payload.get("status") or ""),
            "files": list(payload.get("files") or []),
            "detail": str(payload.get("detail") or ""),
            "success_count": int(payload.get("success_count") or 0),
            "failed_count": int(payload.get("failed_count") or 0),
            "downloaded_file_count": int(payload.get("downloaded_file_count") or 0),
            "total_commands": int(payload.get("total_commands") or 0),
            "current_command_index": int(payload.get("current_command_index") or 0),
            "current_command": str(payload.get("current_command") or ""),
        }

        status_text = str(payload.get("status") or "")
        file_text = "\n".join(payload.get("files") or [])
        self.result_table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
        values = [sn, status_text]

        for column, value in enumerate(values, start=1):
            item = self.result_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                self.result_table.setItem(row, column, item)
            item.setText(value)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._apply_item_color(item, column, value)

        overview_item = self.result_table.item(row, 3)
        if overview_item is None:
            overview_item = QTableWidgetItem()
            self.result_table.setItem(row, 3, overview_item)
        self._update_overview_item(overview_item, payload, file_text)
        self._update_result_row_height(row)

        current_row = self.result_table.currentRow()
        if current_row == row:
            self._update_detail_view(sn)

    def on_result_item_double_clicked(self, item):
        if item is None:
            return
        text = item.text() or ""
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self.show_success("已复制单元格内容", 1200)

    def on_result_selection_changed(self):
        row = self.result_table.currentRow()
        if row < 0:
            self._update_detail_view()
            return
        sn_item = self.result_table.item(row, 1)
        sn = sn_item.text().strip() if sn_item is not None else ""
        self._update_detail_view(sn)

    def on_summary_ready(self, summary: dict):
        if summary.get("cancelled"):
            prefix = "重试已取消" if self._current_run_mode == "retry" else "执行已取消"
            message = (
                f"{prefix}：共 {summary.get('total', 0)} 台，"
                f"已完成 {int(summary.get('success_devices', 0)) + int(summary.get('partial_devices', 0))} 台，"
                f"下载文件 {summary.get('total_files', 0)} 个，"
                f"耗时 {self._format_duration(summary.get('duration_seconds', 0.0))}"
            )
            self.summary_label.setText(message)
            self.show_warning(message, 5000)
            return
        completed_devices = int(summary.get("success_devices", 0)) + int(summary.get("partial_devices", 0))
        failed_devices = int(summary.get("total", 0)) - completed_devices
        prefix = "重试完成" if self._current_run_mode == "retry" else "执行完成"
        message = (
            f"{prefix}：共 {summary.get('total', 0)} 台，"
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
        self._update_result_selection_state()

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

    def fast_cleanup(self):
        if self.worker_thread is not None and self.worker_thread.isRunning():
            try:
                self.fetch_running = False
                self.fetch_canceling = True
                self.worker_thread.cancel()
                self.worker_thread.wait(500)
            except Exception:
                pass

    def _prepare_result_table(self, sn_list):
        self._row_map = {}
        self._device_payloads = {}
        self.result_table.setRowCount(0)
        for row, sn in enumerate(sn_list):
            self.result_table.insertRow(row)
            self._row_map[sn] = row
            self.result_table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
            self.result_table.setCellWidget(row, 0, self._create_result_checkbox_widget())
            initial_values = [sn, "等待执行", ""]
            for column, value in enumerate(initial_values, start=1):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setData(RICH_TEXT_ROLE, [])
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._apply_item_color(item, column, value)
                self.result_table.setItem(row, column, item)
            self._update_result_row_height(row)
        if sn_list:
            self.result_table.selectRow(0)
            self._update_detail_view(sn_list[0])
        else:
            self._update_detail_view()
        self._apply_result_column_widths()
        self._update_result_selection_state()

    def _prepare_retry_rows(self, sn_list):
        total_commands = len(self.get_command_list())
        for sn in sn_list:
            row = self._row_map.get(sn)
            if row is None:
                continue
            self._device_payloads[sn] = {
                "sn": sn,
                "status": "等待执行",
                "files": [],
                "detail": "",
                "success_count": 0,
                "failed_count": 0,
                "downloaded_file_count": 0,
                "total_commands": total_commands,
                "current_command_index": 0,
                "current_command": "",
            }
            for column, value in ((1, sn), (2, "等待执行"), (3, "")):
                item = self.result_table.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.result_table.setItem(row, column, item)
                item.setText(value)
                item.setToolTip(value)
                if column == 3:
                    item.setData(RICH_TEXT_ROLE, [])
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._apply_item_color(item, column, value)
            self._update_result_row_height(row)

        if sn_list:
            first_sn = sn_list[0]
            row = self._row_map.get(first_sn, -1)
            if row >= 0:
                self.result_table.selectRow(row)
            self._update_detail_view(first_sn)
        self._update_result_selection_state()

    def _set_running_state(self, running: bool):
        self.fetch_btn.setEnabled(True)
        self.choose_download_path_btn.setEnabled(not running)
        self.command_edit_btn.setEnabled(not running)
        self.command_input.setEnabled(not running)
        self.sn_input.setEnabled(not running)
        self._set_result_checkboxes_enabled(not running)
        self.result_select_all_checkbox.setEnabled(not running and self.result_table.rowCount() > 0)
        self.result_corner_checkbox.setEnabled(not running and self.result_table.rowCount() > 0)
        self.retry_btn.setEnabled((not running) and self._has_selected_retryable_rows())
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
            self.fetch_btn.setText("取消")
            self.fetch_btn.setIcon(QIcon(":/icons/common/connectting.png"))
            self.fetch_btn.setToolTip("停止中..." if self.fetch_canceling else "停止执行")
        else:
            self.fetch_btn.setText("发送")
            self.fetch_btn.setIcon(QIcon(":/icons/common/run.png"))
            self.fetch_btn.setToolTip("执行命令")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_result_column_widths()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_result_column_widths)

    def on_result_section_resized(self, logical_index, _old_size, _new_size):
        if self._resizing_columns or not hasattr(self, "result_table"):
            return

        viewport_width = self.result_table.viewport().width()
        if viewport_width <= 0:
            return

        self._resizing_columns = True
        try:
            widths = [self.result_table.columnWidth(index) for index in range(self.result_table.columnCount())]
            minimum = self.RESULT_MIN_WIDTHS.get(logical_index, 80)
            widths[logical_index] = max(minimum, widths[logical_index])

            total_width = sum(widths)
            if total_width > viewport_width:
                excess = total_width - viewport_width
                for index in range(self.result_table.columnCount()):
                    if index == logical_index or excess <= 0:
                        continue
                    min_width = self.RESULT_MIN_WIDTHS.get(index, 80)
                    shrinkable = max(0, widths[index] - min_width)
                    if shrinkable <= 0:
                        continue
                    shrink = min(shrinkable, excess)
                    widths[index] -= shrink
                    excess -= shrink

                if excess > 0:
                    widths[logical_index] = max(minimum, widths[logical_index] - excess)

            remaining = viewport_width - sum(widths)
            if remaining > 0:
                widths[-1] += remaining

            for index, width in enumerate(widths):
                self.result_table.setColumnWidth(index, width)
        finally:
            self._resizing_columns = False

    def _apply_plain_toolbar_style(self, frame):
        """工具条容器不显示外层边框。"""
        frame.setStyleSheet("border: none; background: transparent;")

    def refresh_theme(self):
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for card in self._cards:
            self._apply_card_style(card)
        if hasattr(self, "bottom_frame"):
            self._apply_plain_toolbar_style(self.bottom_frame)
        if hasattr(self, "sn_input"):
            self._apply_plain_text_edit_style(self.sn_input)
        if hasattr(self, "command_input"):
            self._apply_plain_text_edit_style(self.command_input)
        if hasattr(self, "download_path_label"):
            self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())
        if hasattr(self, "summary_label"):
            self.summary_label.setStyleSheet("margin: 0px; padding: 0px; border: none;")
        if hasattr(self, "detail_header_label"):
            self.detail_header_label.setStyleSheet("margin: 0px; padding: 0px; border: none;")
        if hasattr(self, "result_selection_label"):
            self.result_selection_label.setStyleSheet(f"color: {t('text_secondary')}; border: none;")
        if hasattr(self, "detail_view"):
            self._apply_rich_text_edit_style(self.detail_view)
        if hasattr(self, "result_table"):
            self._apply_table_style()
            for row in range(self.result_table.rowCount()):
                for column in range(self.result_table.columnCount()):
                    item = self.result_table.item(row, column)
                    if item is None:
                        continue
                    self._apply_item_color(item, column, item.text())
                sn_item = self.result_table.item(row, 1)
                payload = self._device_payloads.get(sn_item.text().strip() if sn_item is not None else "")
                overview_item = self.result_table.item(row, 3)
                if payload and overview_item is not None:
                    self._update_overview_item(overview_item, payload, "\n".join(payload.get("files") or []))
                self._update_result_row_height(row)
            self.result_table.viewport().update()
        current_row = self.result_table.currentRow() if hasattr(self, "result_table") else -1
        if current_row >= 0:
            sn_item = self.result_table.item(current_row, 1)
            self._update_detail_view(sn_item.text().strip() if sn_item is not None else "")
        else:
            self._update_detail_view()

    def _restore_current_detail_view(self):
        if not hasattr(self, "result_table"):
            return

        current_row = self.result_table.currentRow()
        if current_row < 0 and self.result_table.rowCount() > 0:
            current_row = 0
            self.result_table.selectRow(current_row)

        if current_row < 0:
            self._update_detail_view()
            return

        sn_item = self.result_table.item(current_row, 1)
        sn = sn_item.text().strip() if sn_item is not None else ""
        self._update_detail_view(sn)

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
    def _get_plain_text_edit_stylesheet():
        return StyleManager.get_PLAINTEXT_EDIT_TABLE()

    @staticmethod
    def _get_rich_text_edit_stylesheet():
        return StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit")

    @staticmethod
    def _get_context_menu_stylesheet():
        return f"""
        QMenu {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            padding: 2px;
        }}
        QMenu::item {{
            padding: 6px 18px 6px 8px;
            margin: 1px 2px;
            border-radius: 2px;
        }}
        QMenu::item:selected {{
            background-color: {t('selection_bg')};
            color: {t('text_primary')};
        }}
        """

    @classmethod
    def _default_command_list(cls):
        return list(cls.DEFAULT_LOG_COMMANDS[:cls.MAX_COMMANDS])

    @classmethod
    def _normalize_command_list(cls, commands):
        normalized_commands = []
        for command in list(commands or [])[:cls.MAX_COMMANDS]:
            text = str(command or "").strip()
            if text:
                normalized_commands.append(text)
        return normalized_commands

    @classmethod
    def _resolve_initial_command_list(cls, app_config):
        commands = cls._normalize_command_list(app_config.log_commands)
        should_save = False

        if not app_config.log_commands_initialized:
            if commands:
                app_config.log_commands = list(commands)
            else:
                commands = cls._default_command_list()
                app_config.log_commands = list(commands)
            app_config.log_commands_initialized = True
            should_save = True

        return commands, should_save

    def _set_command_list(self, commands):
        normalized_commands = self._normalize_command_list(commands)
        self._commands_updating = True
        try:
            self.command_input.setPlainText("\n".join(normalized_commands))
        finally:
            self._commands_updating = False

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

        total_ratio = 3 + 2 + 4
        selector_width = self.RESULT_MIN_WIDTHS[0]
        remaining_width = max(0, viewport_width - selector_width)
        unit = max(1, remaining_width // total_ratio)
        sn_width = max(self.RESULT_MIN_WIDTHS[1], unit * 3)
        status_width = max(self.RESULT_MIN_WIDTHS[2], unit * 2)
        overview_width = max(self.RESULT_MIN_WIDTHS[3], viewport_width - selector_width - sn_width - status_width)
        self.result_table.setColumnWidth(0, selector_width)
        self.result_table.setColumnWidth(1, sn_width)
        self.result_table.setColumnWidth(2, status_width)
        self.result_table.setColumnWidth(3, overview_width)
        for row in range(self.result_table.rowCount()):
            self._update_result_row_height(row)

    @staticmethod
    def _summarize_multiline_text(lines, empty_text=""):
        normalized = [str(line).strip() for line in lines if str(line).strip()]
        if not normalized:
            return empty_text

        first = normalized[0]
        if len(first) > 44:
            first = f"{first[:41]}..."
        if len(normalized) == 1:
            return first
        return f"{first} 等{len(normalized)}条"

    def _build_overview_text(self, payload: dict) -> str:
        total_commands = int(payload.get("total_commands") or 0)
        success_count = int(payload.get("success_count") or 0)
        failed_count = int(payload.get("failed_count") or 0)
        downloaded_file_count = int(payload.get("downloaded_file_count") or 0)
        current_command_index = int(payload.get("current_command_index") or 0)
        status_text = str(payload.get("status") or "").strip()

        lines = []
        if status_text.startswith("执行中") and total_commands > 0:
            progress = current_command_index or min(total_commands, success_count + failed_count + 1)
            lines.append(f"执行进度 {min(progress, total_commands)}/{total_commands}")
        elif status_text in ("完成", "部分完成", "失败", "已取消") and total_commands > 0:
            lines.append(f"执行情况 {success_count}/{total_commands}")
        elif total_commands > 0 and (success_count > 0 or failed_count > 0):
            lines.append(f"执行情况 {success_count}/{total_commands}")
        else:
            lines.append("-")

        if downloaded_file_count > 0:
            lines.append(f"下载情况 {downloaded_file_count}")
        return "  |  ".join(lines)

    def _build_overview_segments(self, payload: dict):
        if self._should_inline_single_syscmd_overview(payload):
            detail_text = self._extract_inline_syscmd_result_text(payload)
            detail_segments = self._build_detail_segments(detail_text)
            if detail_segments:
                return detail_segments

        overview_text = self._build_overview_text(payload)
        if not overview_text.strip():
            return []
        return [{"text": overview_text, "color": t("text_primary")}]

    def _update_overview_item(self, item: QTableWidgetItem, payload: dict, file_text: str = ""):
        overview_segments = self._build_overview_segments(payload)
        overview_text = self._segments_to_plain_text(overview_segments)
        item.setText(overview_text)
        item.setToolTip(overview_text if not file_text else f"{overview_text}\n{file_text}".strip())
        item.setData(RICH_TEXT_ROLE, overview_segments)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._apply_item_color(item, 3, overview_text)

    def _update_result_row_height(self, row: int):
        if not hasattr(self, "result_table"):
            return
        if row < 0 or row >= self.result_table.rowCount():
            return
        self.result_table.resizeRowToContents(row)
        self.result_table.setRowHeight(row, max(self.RESULT_ROW_HEIGHT, self.result_table.rowHeight(row)))

    @staticmethod
    def _segments_to_plain_text(segments) -> str:
        return "\n".join(str(segment.get("text") or "").strip() for segment in segments if str(segment.get("text") or "").strip())

    @classmethod
    def _should_inline_single_syscmd_overview(cls, payload: dict) -> bool:
        if int(payload.get("total_commands") or 0) != 1:
            return False
        return is_syscmd_family_command(cls._extract_single_syscmd_command(payload))

    @classmethod
    def _extract_single_syscmd_command(cls, payload: dict) -> str:
        current_command = str(payload.get("current_command") or "").strip()
        if current_command:
            return current_command

        for raw_line in str(payload.get("detail") or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("执行命令: "):
                command = line[len("执行命令: "):].strip()
                if is_syscmd_family_command(command):
                    return command
            command_part, separator, _ = line.partition(": ")
            if separator and is_syscmd_family_command(command_part.strip()):
                return command_part.strip()
            if is_syscmd_family_command(line):
                return line
        return ""

    @classmethod
    def _extract_inline_syscmd_result_text(cls, payload: dict) -> str:
        command = cls._extract_single_syscmd_command(payload)
        if not command:
            return ""

        result_lines = []
        for raw_line in str(payload.get("detail") or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("执行命令: "):
                continue
            if line == command:
                continue
            if line.startswith(f"{command}: "):
                line = line[len(command) + 2:].strip()
                if not line:
                    continue
            result_lines.append(line)

        return "\n".join(result_lines)

    def _update_detail_view(self, sn: str = ""):
        if not hasattr(self, "detail_view"):
            return

        payload = self._device_payloads.get((sn or "").strip())
        if not payload:
            self.detail_view.setHtml(
                f'<div style="color: {t("text_secondary")};"><b>设备执行详情</b><br/><br/>选择一台设备后，可在这里查看完整执行详情。</div>'
            )
            return

        files = list(payload.get("files") or [])
        detail_text = str(payload.get("detail") or "").strip()
        file_html = self._render_detail_section(self._build_file_segments(files), "暂无文件结果")
        detail_html = self._render_detail_section(self._build_detail_segments(detail_text), "暂无执行详情")
        self.detail_view.setHtml(
            f"""
            <div style="color: {t('text_primary')};">
                <div><b>SN:</b> {html.escape(str(payload.get('sn') or ''))}</div>
                <div><b>状态:</b> <span style="color: {self._status_color(str(payload.get('status') or ''))};">
                    {html.escape(str(payload.get('status') or ''))}
                </span></div>
                <br/>
                <div><b>文件:</b></div>
                {file_html}
                <br/>
                <div><b>执行详情:</b></div>
                {detail_html}
            </div>
            """
        )

    def _render_detail_section(self, segments, empty_text: str) -> str:
        if not segments:
            return f'<div style="color: {t("text_secondary")};">{html.escape(empty_text)}</div>'
        return "".join(self._render_detail_line_html(str(segment["text"]), str(segment["color"])) for segment in segments)

    def _render_detail_line_html(self, text: str, fallback_color: str) -> str:
        line = str(text or "")
        if line.startswith("执行命令: "):
            command_text = line[len("执行命令: "):]
            return (
                f'<div style="white-space: pre-wrap;">'
                f'<span style="color: {fallback_color};">执行命令: </span>'
                f'<span style="color: {t("status_online")};">{html.escape(command_text)}</span>'
                f'</div>'
            )
        command_part, separator, rest = line.partition(": ")
        if separator and self._looks_like_command_text(command_part):
            command_color = t("status_online")
            if self._detail_line_color(rest) == t("status_offline"):
                command_color = t("status_offline")
            return (
                f'<div style="color: {command_color}; white-space: pre-wrap;">{html.escape(command_part)}</div>'
                f'<div style="color: {fallback_color}; white-space: pre-wrap;">{html.escape(rest)}</div>'
            )
        if separator and line.startswith("执行命令: "):
            return (
                f'<div style="color: {fallback_color}; white-space: pre-wrap;">{html.escape(command_part + separator)}</div>'
                f'<div style="color: {fallback_color}; white-space: pre-wrap;">{html.escape(rest)}</div>'
            )
        if separator and not self._looks_like_command_text(command_part) and "\n" in rest:
            return (
                f'<div style="color: {fallback_color}; white-space: pre-wrap;">{html.escape(command_part + separator)}</div>'
                f'<div style="color: {fallback_color}; white-space: pre-wrap;">{html.escape(rest)}</div>'
            )
        if self._looks_like_command_text(line.strip()):
            command_color = t("status_online")
            if self._detail_line_color(line) == t("status_offline"):
                command_color = t("status_offline")
            return (
                f'<div style="white-space: pre-wrap;">'
                f'<span style="color: {command_color};">{html.escape(line)}</span>'
                f'</div>'
            )
        return (
            f'<div style="color: {fallback_color}; white-space: pre-wrap;">'
            f'{html.escape(line)}</div>'
        )

    @staticmethod
    def _looks_like_command_text(text: str) -> bool:
        normalized = str(text or "").strip().lower()
        return normalized.startswith(("syscmd ", "syscmdex ", "getsystemcfg ", "start"))

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
        if column == 2:
            item.setForeground(self._create_brush(self._status_color(value)))
            return
        item.setForeground(self._create_brush(t("text_primary")))

    def _create_result_checkbox_widget(self):
        checkbox = CheckBox()
        checkbox.stateChanged.connect(self.on_result_checkbox_state_changed)
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(checkbox, 0, Qt.AlignCenter)
        return widget

    def _iter_result_checkboxes(self):
        for row in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(row, 0)
            if widget is None:
                continue
            checkbox = widget.findChild(CheckBox)
            if checkbox is not None:
                yield row, checkbox

    def _set_result_checkboxes_enabled(self, enabled: bool):
        for _, checkbox in self._iter_result_checkboxes():
            checkbox.setEnabled(bool(enabled))

    def on_result_select_all_changed(self, state):
        if self._result_checkbox_updating:
            return
        self._set_all_result_checkboxes(state == Qt.Checked)

    def on_corner_select_all_changed(self, state):
        if self._result_checkbox_updating:
            return
        self._set_all_result_checkboxes(state == Qt.Checked)

    def on_result_checkbox_state_changed(self):
        if self._result_checkbox_updating:
            return
        self._update_result_selection_state()

    def _set_all_result_checkboxes(self, checked: bool):
        self._result_checkbox_updating = True
        try:
            for _, checkbox in self._iter_result_checkboxes():
                checkbox.setChecked(bool(checked))
        finally:
            self._result_checkbox_updating = False
        self._update_result_selection_state()

    def _selected_result_rows(self):
        rows = []
        for row, checkbox in self._iter_result_checkboxes():
            if checkbox.isChecked():
                rows.append(row)
        return rows

    def _is_retryable_status(self, status: str) -> bool:
        status = (status or "").strip()
        if not status:
            return False
        if status.startswith("执行中") or status in ("等待执行", "查询设备密码中", "连接设备中", "正在注销", "已取消"):
            return False
        return status not in ("完成", "部分完成")

    def _get_selected_retryable_sns(self):
        sn_list = []
        for row in self._selected_result_rows():
            status_item = self.result_table.item(row, 2)
            sn_item = self.result_table.item(row, 1)
            status_text = status_item.text().strip() if status_item is not None else ""
            sn = sn_item.text().strip() if sn_item is not None else ""
            if sn and self._is_retryable_status(status_text):
                sn_list.append(sn)
        return sn_list

    def _has_selected_retryable_rows(self) -> bool:
        return bool(self._get_selected_retryable_sns())

    def _update_result_selection_state(self):
        total = self.result_table.rowCount()
        selected_rows = self._selected_result_rows()
        selected_count = len(selected_rows)
        retryable_count = len(self._get_selected_retryable_sns())

        self._result_checkbox_updating = True
        try:
            enabled = (not self.fetch_running) and total > 0
            self.result_select_all_checkbox.setEnabled(enabled)
            self.result_corner_checkbox.setEnabled(enabled)
            all_selected = total > 0 and selected_count == total
            self.result_select_all_checkbox.setChecked(all_selected)
            self.result_corner_checkbox.setChecked(all_selected)
        finally:
            self._result_checkbox_updating = False

        if total <= 0:
            self.result_selection_label.setText("未选择设备")
        elif selected_count <= 0:
            self.result_selection_label.setText(f"已选 0 / {total}")
        else:
            self.result_selection_label.setText(f"已选 {selected_count} / {total}，可重试 {retryable_count} 台")

        self.retry_btn.setEnabled((not self.fetch_running) and retryable_count > 0)

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
