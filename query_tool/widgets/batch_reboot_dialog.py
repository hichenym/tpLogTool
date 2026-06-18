"""
批量重启对话框
支持批量查询在线状态、批量唤醒、批量重启
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHeaderView,
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from query_tool.ui import (
    BodyLabel,
    ElevatedCardWidget,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    RadioButton,
    TableWidget,
)
from query_tool.utils import StyleManager, check_device_online, wake_device_smart
from query_tool.utils.logger import logger
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.utils.thread_manager import ThreadManager
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.widgets.custom_widgets import set_dark_title_bar


class BatchStatusWorker(QObject):
    """批量状态查询工作器"""

    single_result = pyqtSignal(str, bool)  # (sn, is_online)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_query, max_workers=30):
        super().__init__()
        self.devices = devices
        self.device_query = device_query
        self.max_workers = max_workers
        self._stop = False

    def stop(self):
        self._stop = True

    def check_single_device(self, sn, dev_id):
        """查询单个设备在线状态"""
        if self._stop:
            return sn, False
        try:
            is_online = check_device_online(sn, self.device_query, dev_id=dev_id)
            return sn, is_online
        except Exception:
            return sn, False

    def run(self):
        try:
            total = len(self.devices)
            completed = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.check_single_device, sn, dev_id): sn
                    for sn, dev_id, _ in self.devices
                }

                for future in as_completed(futures):
                    if self._stop:
                        break
                    sn, is_online = future.result()
                    self.single_result.emit(sn, is_online)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"查询进度: {completed}/{total}")

            self.all_done.emit()
        except Exception:
            self.all_done.emit()


class BatchStatusThread(QThread):
    """批量状态查询线程"""

    single_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_query, max_workers=30):
        super().__init__()
        self.worker = BatchStatusWorker(devices, device_query, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)

    def run(self):
        self.worker.run()

    def stop(self):
        self.worker.stop()


class BatchWakeWorker(QObject):
    """批量唤醒工作器"""

    single_result = pyqtSignal(str, bool)  # (sn, success)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_query, max_workers=30):
        super().__init__()
        self.devices = devices
        self.device_query = device_query
        self.max_workers = max_workers
        self._stop = False

    def stop(self):
        self._stop = True

    def wake_single_device(self, sn, dev_id):
        """唤醒单个设备"""
        if self._stop:
            return sn, False
        try:
            success = wake_device_smart(dev_id, sn, self.device_query, max_times=3)
            return sn, success
        except Exception:
            return sn, False

    def run(self):
        try:
            total = len(self.devices)
            completed = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.wake_single_device, sn, dev_id): sn
                    for sn, dev_id in self.devices
                }

                for future in as_completed(futures):
                    if self._stop:
                        break
                    sn, success = future.result()
                    self.single_result.emit(sn, success)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"唤醒进度: {completed}/{total}")

            self.all_done.emit()
        except Exception:
            self.all_done.emit()


class BatchWakeThread(QThread):
    """批量唤醒线程"""

    single_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_query, max_workers=30):
        super().__init__()
        self.worker = BatchWakeWorker(devices, device_query, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)

    def run(self):
        self.worker.run()

    def stop(self):
        self.worker.stop()


class BatchRebootWorker(QObject):
    """批量重启工作器"""

    single_result = pyqtSignal(str, str, str)  # (sn, status, message)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, reboot_time, device_query, max_workers=30):
        super().__init__()
        self.devices = devices
        self.reboot_time = reboot_time
        self.device_query = device_query
        self.max_workers = max_workers
        self._stop = False

    def stop(self):
        self._stop = True

    def reboot_single_device(self, sn, dev_id):
        """重启单个设备"""
        if self._stop:
            return sn, "failed", "任务已停止"
        try:
            status, message = self.device_query.send_reboot_command(
                dev_id, self.reboot_time, return_detail=True
            )
            return sn, status, message
        except Exception as e:
            logger.error(f"重启设备 {sn} 出错: {e}")
            return sn, "failed", str(e)

    def run(self):
        try:
            total = len(self.devices)
            completed = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.reboot_single_device, sn, dev_id): sn
                    for sn, dev_id in self.devices
                }

                for future in as_completed(futures):
                    if self._stop:
                        break
                    sn, status, message = future.result()
                    self.single_result.emit(sn, status, message)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"重启进度: {completed}/{total}")

            self.all_done.emit()
        except Exception:
            self.all_done.emit()


class BatchRebootThread(QThread):
    """批量重启线程"""

    single_result = pyqtSignal(str, str, str)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, reboot_time, device_query, max_workers=30):
        super().__init__()
        self.worker = BatchRebootWorker(devices, reboot_time, device_query, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)

    def run(self):
        self.worker.run()

    def stop(self):
        self.worker.stop()


class BatchRebootDialog(AdaptiveDialog):
    """批量重启对话框"""

    def __init__(self, devices, device_query, thread_count, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.device_query = device_query
        self.thread_count = thread_count
        self.parent_window = parent

        self.device_status = {}
        self.command_result_stats = {"success": 0, "offline": 0, "failed": 0}
        self.thread_mgr = ThreadManager()
        self._card_title_labels = []
        self._caption_labels = []

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()
        self.start_initial_query()

    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass

    def _apply_card_title_style(self, label):
        label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")

    def _apply_caption_style(self, label):
        label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")

    def _create_card_section(self, title):
        card = ElevatedCardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = BodyLabel(title)
        self._card_title_labels.append(title_label)
        self._apply_card_title_style(title_label)
        layout.addWidget(title_label)

        if not QFLUENT_WIDGETS_AVAILABLE:
            card.setStyleSheet(
                f"""
                QFrame {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )
        return card, layout

    def _caption_label(self, text, width=None):
        label = BodyLabel(text)
        if width is not None:
            label.setFixedWidth(width)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._caption_labels.append(label)
        self._apply_caption_style(label)
        return label

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_table_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.device_table, "TABLE")

    def _set_status_item(self, item, text, color_role):
        item.setText(text)
        item.setData(Qt.ForegroundRole, QColor(t(color_role)))

    def _apply_status_colors(self):
        role_map = {
            "在线": "status_online",
            "离线": "status_offline",
            "查询中...": "status_pending",
            "唤醒中...": "status_pending",
        }
        for row in range(self.device_table.rowCount()):
            item = self.device_table.item(row, 2)
            if item is None:
                continue
            item.setData(Qt.ForegroundRole, QColor(t(role_map.get(item.text(), "text_hint"))))

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量重启设备")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (700, 520),
            min_size=(540, 380),
            scrollable=True,
            layout_margins=(20, 20, 20, 20),
            spacing=15,
            max_width_ratio=0.84,
            max_height_ratio=0.82,
        )

        device_card, device_layout = self._create_card_section("设备列表")

        info_button_row = QWidget()
        info_button_layout = QHBoxLayout(info_button_row)
        info_button_layout.setContentsMargins(0, 0, 0, 0)
        info_button_layout.setSpacing(10)

        self.stats_label = BodyLabel("正在查询设备状态...")
        self.stats_label.setStyleSheet(
            f"color: {t('status_info')}; font-size: 13px; font-weight: 600; border: none;"
        )

        self.batch_wake_btn = PushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(112, 32)
        self.batch_wake_btn.setEnabled(False)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        self._apply_secondary_button_style(self.batch_wake_btn)

        self.refresh_btn = PushButton("刷新状态")
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(112, 32)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.on_refresh_status)
        self._apply_secondary_button_style(self.refresh_btn)

        info_button_layout.addWidget(self.stats_label)
        info_button_layout.addStretch()
        info_button_layout.addWidget(self.batch_wake_btn)
        info_button_layout.addWidget(self.refresh_btn)
        device_layout.addWidget(info_button_row)

        self.device_table = TableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "在线状态"])
        self.device_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(TableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        self.device_table.setMinimumHeight(220)
        self.device_table.setMaximumHeight(220)
        self._apply_table_style()

        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.device_table.setColumnWidth(2, 140)

        self.device_table.setRowCount(len(self.devices))
        for row, (sn, dev_id, device_name) in enumerate(self.devices):
            self.device_table.setItem(row, 0, QTableWidgetItem(device_name))
            self.device_table.setItem(row, 1, QTableWidgetItem(sn))
            status_item = QTableWidgetItem("查询中...")
            self._set_status_item(status_item, "查询中...", "status_pending")
            self.device_table.setItem(row, 2, status_item)

        device_layout.addWidget(self.device_table)
        layout.addWidget(device_card)

        time_card, time_layout = self._create_card_section("重启时间")

        time_row = QWidget()
        time_row_layout = QHBoxLayout(time_row)
        time_row_layout.setContentsMargins(0, 0, 0, 0)
        time_row_layout.setSpacing(10)

        time_label = self._caption_label("执行时间:", width=70)

        self.time_group = QButtonGroup(self)
        self.now_radio = RadioButton("立即重启")
        self.now_radio.setChecked(True)
        self.now_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")

        self.later_radio = RadioButton("5分钟后重启")
        self.later_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")

        self.time_group.addButton(self.now_radio, 0)
        self.time_group.addButton(self.later_radio, 1)

        time_row_layout.addWidget(time_label)
        time_row_layout.addWidget(self.now_radio)
        time_row_layout.addWidget(self.later_radio)
        time_row_layout.addStretch()

        time_layout.addWidget(time_row)
        layout.addWidget(time_card)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        self.confirm_btn = PrimaryPushButton("开始重启")
        self.confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.confirm_btn.setIconSize(QSize(18, 18))
        self.confirm_btn.setFixedSize(108, 34)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.on_confirm)

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(18, 18))
        self.cancel_btn.setFixedSize(92, 34)
        self.cancel_btn.clicked.connect(self.reject)
        self._apply_secondary_button_style(self.cancel_btn)

        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def start_initial_query(self):
        """开始初始查询"""
        thread = BatchStatusThread(
            self.devices,
            self.device_query,
            self.thread_count,
        )
        thread.single_result.connect(self.on_status_result)
        thread.all_done.connect(self.on_query_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_status", thread)
        thread.start()

    def on_status_result(self, sn, is_online):
        """单个设备状态查询结果"""
        self.device_status[sn] = is_online

        for row in range(self.device_table.rowCount()):
            sn_item = self.device_table.item(row, 1)
            if sn_item and sn_item.text() == sn:
                status_item = self.device_table.item(row, 2)
                if is_online:
                    self._set_status_item(status_item, "在线", "status_online")
                else:
                    self._set_status_item(status_item, "离线", "status_offline")
                break

    def on_query_complete(self):
        """查询完成"""
        self.update_stats()
        self.batch_wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)

    def update_stats(self):
        """更新统计信息"""
        online_count = sum(1 for status in self.device_status.values() if status)
        offline_count = len(self.device_status) - online_count
        self.stats_label.setText(f"{online_count} 台将重启  |  {offline_count} 台跳过")

    def on_batch_wake(self):
        """批量唤醒"""
        offline_devices = []
        for sn, dev_id, device_name in self.devices:
            if not self.device_status.get(sn, False):
                offline_devices.append((sn, dev_id))

        if not offline_devices:
            if self.parent_window:
                self.parent_window.show_info("没有离线设备需要唤醒")
            return

        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)

        for sn, _ in offline_devices:
            for row in range(self.device_table.rowCount()):
                sn_item = self.device_table.item(row, 1)
                if sn_item and sn_item.text() == sn:
                    status_item = self.device_table.item(row, 2)
                    self._set_status_item(status_item, "唤醒中...", "status_pending")
                    break

        thread = BatchWakeThread(
            offline_devices,
            self.device_query,
            self.thread_count,
        )
        thread.all_done.connect(self.on_wake_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_wake", thread)
        thread.start()

    def on_wake_complete(self):
        """唤醒完成，自动刷新状态"""
        self.on_refresh_status()

    def on_refresh_status(self):
        """刷新状态"""
        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)

        for row in range(self.device_table.rowCount()):
            status_item = self.device_table.item(row, 2)
            self._set_status_item(status_item, "查询中...", "status_pending")

        self.stats_label.setText("正在查询设备状态...")

        thread = BatchStatusThread(
            self.devices,
            self.device_query,
            self.thread_count,
        )
        thread.single_result.connect(self.on_status_result)
        thread.all_done.connect(self.on_query_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_status_refresh", thread)
        thread.start()

    def on_confirm(self):
        """确认重启"""
        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.command_result_stats = {"success": 0, "offline": 0, "failed": 0}

        thread = BatchStatusThread(
            self.devices,
            self.device_query,
            self.thread_count,
        )
        thread.single_result.connect(self.on_status_result_silent)
        thread.all_done.connect(self.on_final_query_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("final_status_query", thread)
        thread.start()

    def on_status_result_silent(self, sn, is_online):
        """静默更新设备状态（不更新表格显示）"""
        self.device_status[sn] = is_online

    def on_final_query_complete(self):
        """最终查询完成，开始重启"""
        reboot_time = "now" if self.now_radio.isChecked() else "after_five_minute"

        thread = BatchRebootThread(
            [(sn, dev_id) for sn, dev_id, _ in self.devices],
            reboot_time,
            self.device_query,
            self.thread_count,
        )
        thread.single_result.connect(self.on_reboot_result)
        thread.all_done.connect(self.on_reboot_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_reboot", thread)
        thread.start()

    def on_reboot_result(self, sn, status, message):
        """单台重启结果"""
        if status not in self.command_result_stats:
            status = "failed"
        self.command_result_stats[status] += 1

    def on_reboot_complete(self):
        """重启完成"""
        success_count = self.command_result_stats.get("success", 0)
        offline_count = self.command_result_stats.get("offline", 0)
        failed_count = self.command_result_stats.get("failed", 0)

        if success_count > 0:
            if self.parent_window:
                self.parent_window.show_success(
                    f"重启命令下发完成：成功 {success_count} 台，离线 {offline_count} 台，失败 {failed_count} 台"
                )
            self.accept()
            return

        if offline_count > 0 and failed_count == 0:
            if self.parent_window:
                self.parent_window.show_error("设备离线，操作失败")
        else:
            if self.parent_window:
                self.parent_window.show_error(
                    f"重启下发失败：离线 {offline_count} 台，失败 {failed_count} 台"
                )
        self.restore_buttons()

    def restore_buttons(self):
        """恢复按钮状态"""
        self.batch_wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

    def closeEvent(self, event):
        """关闭事件"""
        self.thread_mgr.stop_all()
        event.accept()

    def refresh_theme(self):
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for label in self._caption_labels:
            self._apply_caption_style(label)

        if hasattr(self, "stats_label"):
            self.stats_label.setStyleSheet(
                f"color: {t('status_info')}; font-size: 13px; font-weight: 600; border: none;"
            )
        if hasattr(self, "batch_wake_btn"):
            self._apply_secondary_button_style(self.batch_wake_btn)
        if hasattr(self, "refresh_btn"):
            self._apply_secondary_button_style(self.refresh_btn)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
        if hasattr(self, "device_table"):
            self._apply_table_style()
            self._apply_status_colors()
        if hasattr(self, "now_radio"):
            self.now_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, "later_radio"):
            self.later_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
