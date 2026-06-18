"""
批量设备固件升级对话框
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHeaderView,
    QHBoxLayout,
    QRadioButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .adaptive_dialog import AdaptiveDialog
from .custom_widgets import set_dark_title_bar
from query_tool.ui import (
    BodyLabel,
    ComboBox,
    ElevatedCardWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    RadioButton,
    TableWidget,
)
from query_tool.utils import StyleManager
from query_tool.utils.logger import logger
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.utils.thread_manager import ThreadManager
from query_tool.utils.upgrade_service import prepare_and_send_upgrade


class NoWheelComboBox(ComboBox):
    """禁用鼠标滚轮切换的下拉框"""

    def wheelEvent(self, event):
        event.ignore()


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
            from query_tool.utils import check_device_online

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
                    for sn, dev_id, _, _ in self.devices
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
            from query_tool.utils import wake_device_smart

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


class FirmwareQueryThread(QThread):
    """固件查询线程"""

    finished_signal = pyqtSignal(list, int, int)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)

    def __init__(self, create_user="cur", device_identify="", audit_result="", page=1, per_page=100):
        super().__init__()
        self.create_user = create_user
        self.device_identify = device_identify
        self.audit_result = audit_result
        self.page = page
        self.per_page = per_page

    def run(self):
        try:
            self.progress_signal.emit("正在查询固件数据...")
            from query_tool.utils.firmware_api import fetch_firmware_data

            result = fetch_firmware_data(
                create_user=self.create_user,
                device_identify=self.device_identify,
                audit_result=self.audit_result,
                page=self.page,
                per_page=self.per_page,
            )

            if result is None or len(result) != 3:
                self.error_signal.emit("获取固件数据失败：返回值格式错误")
                return

            firmware_list, total_count, total_pages = result

            if firmware_list is None:
                self.error_signal.emit("获取固件数据失败")
                return

            self.finished_signal.emit(firmware_list, total_count, total_pages)

        except Exception as e:
            import traceback

            traceback.print_exc()
            self.error_signal.emit(f"查询出错: {str(e)}")


class BatchUpgradeWorker(QObject):
    """批量升级工作器"""

    single_result = pyqtSignal(str, str, str)  # (sn, status, message)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_identify, file_url, device_query=None, token=None, host=None, max_workers=30):
        super().__init__()
        self.devices = devices
        self.device_identify = device_identify
        self.file_url = file_url
        self.device_query = device_query
        self.token = token or (device_query.token if device_query else None)
        self.host = host or (device_query.host if device_query else "console.seetong.com")
        self.max_workers = max_workers
        self._stop = False

    def stop(self):
        self._stop = True

    def upgrade_single_device(self, sn, dev_id):
        """升级单个设备"""
        if self._stop:
            return sn, "failed", "任务已停止"
        try:
            status, message = prepare_and_send_upgrade(
                sn,
                dev_id,
                self.device_identify,
                self.file_url,
                device_query=self.device_query,
                token=self.token,
                host=self.host,
                max_wake_times=3,
            )
            return sn, status, message
        except Exception as e:
            logger.error(f"升级设备 {sn} 出错: {e}")
            return sn, "failed", str(e)

    def run(self):
        try:
            total = len(self.devices)
            completed = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.upgrade_single_device, sn, dev_id): sn
                    for sn, dev_id in self.devices
                }

                for future in as_completed(futures):
                    if self._stop:
                        break
                    sn, status, message = future.result()
                    self.single_result.emit(sn, status, message)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"升级进度: {completed}/{total}")

            self.all_done.emit()
        except Exception:
            self.all_done.emit()


class BatchUpgradeThread(QThread):
    """批量升级线程"""

    single_result = pyqtSignal(str, str, str)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)

    def __init__(self, devices, device_identify, file_url, device_query=None, token=None, host=None, max_workers=30):
        super().__init__()
        self.worker = BatchUpgradeWorker(
            devices,
            device_identify,
            file_url,
            device_query=device_query,
            token=token,
            host=host,
            max_workers=max_workers,
        )
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)

    def run(self):
        self.worker.run()

    def stop(self):
        self.worker.stop()


class BatchUpgradeDialog(AdaptiveDialog):
    """批量设备固件升级对话框"""

    def __init__(self, devices, device_query, thread_count, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.device_query = device_query
        self.thread_count = thread_count
        self.parent_window = parent

        models = set(model for _, _, _, model in devices)
        self.has_single_model = len(models) == 1
        self.device_model = list(models)[0] if self.has_single_model else ""

        self.device_status = {}
        self.firmware_list = []
        self.selected_firmware = None
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self.command_result_stats = {"success": 0, "offline": 0, "wake_failed": 0, "failed": 0}

        self.thread_mgr = ThreadManager()
        self._card_title_labels = []
        self._caption_labels = []
        self._info_labels = []

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()
        self.start_initial_query()

        if self.has_single_model:
            self.query_firmware()

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

    def _apply_info_style(self, label):
        label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")

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

    def _info_label(self, text):
        label = BodyLabel(text)
        self._info_labels.append(label)
        self._apply_info_style(label)
        return label

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_combo_style(self, combo):
        if not QFLUENT_WIDGETS_AVAILABLE:
            combo.setStyleSheet(StyleManager.get_COMBOBOX())

    def _apply_read_only_line_edit_style(self, widget):
        if not QFLUENT_WIDGETS_AVAILABLE:
            widget.setStyleSheet(StyleManager.get_READONLY_INPUT())

    def _apply_table_style(self, table):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(table, "TABLE")

    def _set_device_status_item(self, item, text, color_role):
        item.setText(text)
        item.setData(Qt.ForegroundRole, QColor(t(color_role)))

    def _apply_device_status_colors(self):
        role_map = {
            "在线": "status_online",
            "离线": "status_offline",
            "唤醒中...": "status_pending",
            "查询中...": "status_pending",
        }
        for row in range(self.device_table.rowCount()):
            item = self.device_table.item(row, 3)
            if item is None:
                continue
            item.setData(Qt.ForegroundRole, QColor(t(role_map.get(item.text(), "text_hint"))))

    def _apply_audit_result_colors(self):
        audit_result_color_map = {
            "无需审核": t("text_hint"),
            "待审核": t("status_pending"),
            "审核通过": t("status_online"),
            "审核不通过": t("status_offline"),
        }
        for row in range(self.firmware_table.rowCount()):
            item = self.firmware_table.item(row, 2)
            if item is None:
                continue
            item.setData(Qt.ForegroundRole, QColor(audit_result_color_map.get(item.text(), t("text_hint"))))

    @staticmethod
    def _find_radio_button(widget):
        if widget is None:
            return None
        radio = widget.findChild(RadioButton)
        if radio is not None:
            return radio
        return widget.findChild(QRadioButton)

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量设备固件升级")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (980, 840),
            min_size=(760, 620),
            scrollable=True,
            layout_margins=(20, 20, 20, 20),
            spacing=14,
        )

        device_card, device_layout = self._create_card_section("设备列表")

        device_toolbar = QWidget()
        device_toolbar_layout = QHBoxLayout(device_toolbar)
        device_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        device_toolbar_layout.setSpacing(10)

        self.device_stats_label = BodyLabel("正在查询设备状态...")
        self.device_stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; font-weight: 600; border: none;")

        self.batch_wake_btn = PushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(110, 32)
        self.batch_wake_btn.setEnabled(False)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        self._apply_secondary_button_style(self.batch_wake_btn)

        self.refresh_status_btn = PushButton("刷新状态")
        self.refresh_status_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_status_btn.setIconSize(QSize(16, 16))
        self.refresh_status_btn.setFixedSize(110, 32)
        self.refresh_status_btn.setEnabled(False)
        self.refresh_status_btn.clicked.connect(self.on_refresh_status)
        self._apply_secondary_button_style(self.refresh_status_btn)

        device_toolbar_layout.addWidget(self.device_stats_label)
        device_toolbar_layout.addStretch()
        device_toolbar_layout.addWidget(self.batch_wake_btn)
        device_toolbar_layout.addWidget(self.refresh_status_btn)
        device_layout.addWidget(device_toolbar)

        self.device_table = TableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "型号", "在线状态"])
        self.device_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(TableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        self.device_table.setMinimumHeight(190)
        self.device_table.setMaximumHeight(190)
        self._apply_table_style(self.device_table)

        device_header = self.device_table.horizontalHeader()
        device_header.setSectionResizeMode(0, QHeaderView.Stretch)
        device_header.setSectionResizeMode(1, QHeaderView.Stretch)
        device_header.setSectionResizeMode(2, QHeaderView.Fixed)
        device_header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.device_table.setColumnWidth(2, 140)
        self.device_table.setColumnWidth(3, 120)

        self.device_table.setRowCount(len(self.devices))
        for row, (sn, dev_id, device_name, model) in enumerate(self.devices):
            self.device_table.setItem(row, 0, QTableWidgetItem(device_name))
            self.device_table.setItem(row, 1, QTableWidgetItem(sn))
            self.device_table.setItem(row, 2, QTableWidgetItem(model))
            status_item = QTableWidgetItem("查询中...")
            self._set_device_status_item(status_item, "查询中...", "status_pending")
            self.device_table.setItem(row, 3, status_item)

        device_layout.addWidget(self.device_table)
        layout.addWidget(device_card)

        query_card, query_layout = self._create_card_section("固件查询")

        if not self.has_single_model:
            self.model_hint_label = self._info_label("当前选中的设备型号不一致，仅可查询固件，不能执行批量升级。")
            query_layout.addWidget(self.model_hint_label)

        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(10)

        self.publisher_label = self._caption_label("发布人员:", width=70)
        self.publisher_combo = NoWheelComboBox()
        self.publisher_combo.setFixedHeight(32)
        self.publisher_combo.addItem("当前登录用户", "cur")
        self.publisher_combo.addItem("全部", "all")
        self._apply_combo_style(self.publisher_combo)

        self.audit_label = self._caption_label("审核状态:", width=70)
        self.audit_combo = NoWheelComboBox()
        self.audit_combo.setFixedHeight(32)
        self.audit_combo.addItem("全部", "")
        self.audit_combo.addItem("无需审核", "1")
        self.audit_combo.addItem("待审核", "2")
        self.audit_combo.addItem("审核通过", "3")
        self.audit_combo.addItem("审核不通过", "4")
        self._apply_combo_style(self.audit_combo)

        row1_layout.addWidget(self.publisher_label)
        row1_layout.addWidget(self.publisher_combo, 1)
        row1_layout.addSpacing(8)
        row1_layout.addWidget(self.audit_label)
        row1_layout.addWidget(self.audit_combo, 1)
        query_layout.addWidget(row1)

        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(10)

        self.identifier_label = self._caption_label("固件标识:", width=70)
        self.identifier_input = LineEdit()
        self.identifier_input.setPlaceholderText("输入固件标识...")
        self.identifier_input.setFixedHeight(32)
        if self.has_single_model:
            self.identifier_input.setText(self.device_model)
            self.identifier_input.setReadOnly(True)
            self._apply_read_only_line_edit_style(self.identifier_input)

        row2_layout.addWidget(self.identifier_label)
        row2_layout.addWidget(self.identifier_input, 1)
        row2_layout.addStretch()

        self.query_firmware_btn = PrimaryPushButton("查询")
        self.query_firmware_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_firmware_btn.setIconSize(QSize(16, 16))
        self.query_firmware_btn.setFixedSize(88, 32)
        self.query_firmware_btn.clicked.connect(self.query_firmware)
        row2_layout.addWidget(self.query_firmware_btn)
        query_layout.addWidget(row2)
        layout.addWidget(query_card)

        list_card, list_layout = self._create_card_section("固件列表")
        self.firmware_table = TableWidget()
        self.firmware_table.setColumnCount(6)
        self.firmware_table.setHorizontalHeaderLabels(
            ["选择", "固件标识", "审核结果", "开始时间", "结束时间", "发布备注"]
        )
        self.firmware_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.firmware_table.setSelectionMode(TableWidget.SingleSelection)
        self.firmware_table.setSelectionBehavior(TableWidget.SelectRows)
        self.firmware_table.setFocusPolicy(Qt.StrongFocus)
        self.firmware_table.setMinimumHeight(220)
        self.firmware_table.setMaximumHeight(220)
        self.firmware_table.setWordWrap(True)
        self.firmware_table.setTextElideMode(Qt.ElideRight)
        self.firmware_table.cellClicked.connect(self.on_table_cell_clicked)
        self._apply_table_style(self.firmware_table)

        firmware_header = self.firmware_table.horizontalHeader()
        firmware_header.setSectionResizeMode(0, QHeaderView.Fixed)
        firmware_header.setSectionResizeMode(1, QHeaderView.Interactive)
        firmware_header.setSectionResizeMode(2, QHeaderView.Fixed)
        firmware_header.setSectionResizeMode(3, QHeaderView.Fixed)
        firmware_header.setSectionResizeMode(4, QHeaderView.Fixed)
        firmware_header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.firmware_table.setColumnWidth(0, 56)
        self.firmware_table.setColumnWidth(1, 300)
        self.firmware_table.setColumnWidth(2, 96)
        self.firmware_table.setColumnWidth(3, 100)
        self.firmware_table.setColumnWidth(4, 100)
        list_layout.addWidget(self.firmware_table)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(10)

        self.prev_page_btn = PushButton("上一页")
        self.prev_page_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_page_btn.setIconSize(QSize(18, 18))
        self.prev_page_btn.setFixedSize(92, 32)
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.on_prev_page)
        self._apply_secondary_button_style(self.prev_page_btn)

        self.page_label = BodyLabel("第 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setMinimumWidth(96)
        self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")

        self.next_page_btn = PushButton("下一页")
        self.next_page_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_page_btn.setIconSize(QSize(18, 18))
        self.next_page_btn.setLayoutDirection(Qt.RightToLeft)
        self.next_page_btn.setFixedSize(92, 32)
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.on_next_page)
        self._apply_secondary_button_style(self.next_page_btn)

        self.firmware_stats_label = BodyLabel("未选择固件")
        self.firmware_stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")

        footer_layout.addWidget(self.prev_page_btn)
        footer_layout.addWidget(self.page_label)
        footer_layout.addWidget(self.next_page_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self.firmware_stats_label)
        list_layout.addLayout(footer_layout)
        layout.addWidget(list_card)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        self.confirm_btn = PrimaryPushButton("开始升级")
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
        """开始初始查询设备状态"""
        thread = BatchStatusThread(self.devices, self.device_query, self.thread_count)
        thread.single_result.connect(self.on_status_result)
        thread.all_done.connect(self.on_status_query_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_status", thread)
        thread.start()

    def on_status_result(self, sn, is_online):
        """单个设备状态查询结果"""
        self.device_status[sn] = is_online

        for row in range(self.device_table.rowCount()):
            sn_item = self.device_table.item(row, 1)
            if sn_item and sn_item.text() == sn:
                status_item = self.device_table.item(row, 3)
                if is_online:
                    self._set_device_status_item(status_item, "在线", "status_online")
                else:
                    self._set_device_status_item(status_item, "离线", "status_offline")
                break

    def on_status_query_complete(self):
        """设备状态查询完成"""
        self.update_device_stats()
        self.batch_wake_btn.setEnabled(True)
        self.refresh_status_btn.setEnabled(True)

    def update_device_stats(self):
        """更新设备统计信息"""
        online_count = sum(1 for status in self.device_status.values() if status)
        offline_count = len(self.device_status) - online_count
        self.device_stats_label.setText(f"{online_count} 台在线  |  {offline_count} 台离线")

    def on_batch_wake(self):
        """批量唤醒"""
        offline_devices = []
        for sn, dev_id, device_name, model in self.devices:
            if not self.device_status.get(sn, False):
                offline_devices.append((sn, dev_id))

        if not offline_devices:
            if self.parent_window:
                self.parent_window.show_info("没有离线设备需要唤醒")
            return

        self.batch_wake_btn.setEnabled(False)
        self.refresh_status_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)

        for sn, _ in offline_devices:
            for row in range(self.device_table.rowCount()):
                sn_item = self.device_table.item(row, 1)
                if sn_item and sn_item.text() == sn:
                    status_item = self.device_table.item(row, 3)
                    self._set_device_status_item(status_item, "唤醒中...", "status_pending")
                    break

        thread = BatchWakeThread(offline_devices, self.device_query, self.thread_count)
        thread.all_done.connect(self.on_wake_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_wake", thread)
        thread.start()

    def on_wake_complete(self):
        """唤醒完成，自动刷新状态"""
        self.on_refresh_status()

    def on_refresh_status(self):
        """刷新设备状态"""
        self.batch_wake_btn.setEnabled(False)
        self.refresh_status_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)

        for row in range(self.device_table.rowCount()):
            status_item = self.device_table.item(row, 3)
            self._set_device_status_item(status_item, "查询中...", "status_pending")

        self.device_stats_label.setText("正在查询设备状态...")

        thread = BatchStatusThread(self.devices, self.device_query, self.thread_count)
        thread.single_result.connect(self.on_status_result)
        thread.all_done.connect(self.on_status_query_complete)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("batch_status_refresh", thread)
        thread.start()

    def query_firmware(self, page=None):
        """查询固件列表"""
        if page is None:
            page = self.current_page

        create_user = self.publisher_combo.currentData()
        audit_result = self.audit_combo.currentData()
        device_identify = self.identifier_input.text().strip()

        self.query_firmware_btn.setEnabled(False)

        if self.parent_window:
            self.parent_window.show_progress("正在查询固件数据...")

        thread = FirmwareQueryThread(
            create_user=create_user,
            device_identify=device_identify,
            audit_result=audit_result,
            page=page,
            per_page=100,
        )
        thread.finished_signal.connect(self.on_firmware_query_finished)
        thread.error_signal.connect(self.on_firmware_query_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("firmware_query", thread)
        thread.start()

    def on_firmware_query_finished(self, firmware_list, total_count, total_pages):
        """固件查询完成"""
        self.firmware_list = firmware_list
        self.total_count = total_count
        self.total_pages = total_pages
        self.query_firmware_btn.setEnabled(True)

        if self.parent_window:
            self.parent_window.show_success(f"查询到 {total_count} 条固件数据")

        self.update_firmware_table()
        self.update_page_controls()

    def on_firmware_query_error(self, error_msg):
        """固件查询错误"""
        self.query_firmware_btn.setEnabled(True)

        if self.parent_window:
            self.parent_window.show_error(f"查询失败: {error_msg}")

    def update_firmware_table(self):
        """更新固件表格"""
        self.firmware_table.setRowCount(len(self.firmware_list))

        start_index = (self.current_page - 1) * 100 + 1
        audit_result_color_map = {
            "无需审核": t("text_hint"),
            "待审核": t("status_pending"),
            "审核通过": t("status_online"),
            "审核不通过": t("status_offline"),
        }

        self.radio_group = QButtonGroup(self)
        self.radio_group.buttonClicked.connect(self.on_firmware_selected)

        for row, firmware in enumerate(self.firmware_list):
            self.firmware_table.setVerticalHeaderItem(row, QTableWidgetItem(str(start_index + row)))

            radio = RadioButton()
            radio_widget = QWidget()
            radio_layout = QHBoxLayout(radio_widget)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            radio_layout.addWidget(radio)
            radio_layout.setAlignment(Qt.AlignCenter)
            self.firmware_table.setCellWidget(row, 0, radio_widget)
            self.radio_group.addButton(radio, row)

            identifier_item = QTableWidgetItem(firmware.get("identifier", ""))
            identifier_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.firmware_table.setItem(row, 1, identifier_item)

            audit_result = firmware.get("audit_result", "")
            audit_item = QTableWidgetItem(audit_result)
            audit_item.setTextAlignment(Qt.AlignCenter)
            audit_item.setData(Qt.ForegroundRole, QColor(audit_result_color_map.get(audit_result, t("text_hint"))))
            self.firmware_table.setItem(row, 2, audit_item)

            start_time_item = QTableWidgetItem(firmware.get("start_time", ""))
            start_time_item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 3, start_time_item)

            end_time_item = QTableWidgetItem(firmware.get("end_time", ""))
            end_time_item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 4, end_time_item)

            remark_item = QTableWidgetItem(firmware.get("remark", ""))
            remark_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.firmware_table.setItem(row, 5, remark_item)

        self.firmware_table.resizeRowsToContents()

    def on_firmware_selected(self, button):
        """固件选择事件"""
        row = self.radio_group.id(button)
        if 0 <= row < len(self.firmware_list):
            self.selected_firmware = self.firmware_list[row]
            device_identify = self.selected_firmware.get("identifier", "")
            self.firmware_stats_label.setText(f"已选择: {device_identify}")
            self.update_confirm_button()
            self.firmware_table.selectRow(row)

    def on_table_cell_clicked(self, row, column):
        """表格单元格点击事件"""
        if 0 <= row < len(self.firmware_list):
            radio_widget = self.firmware_table.cellWidget(row, 0)
            radio = self._find_radio_button(radio_widget)
            if radio is None:
                return
            radio.setChecked(True)
            self.selected_firmware = self.firmware_list[row]
            device_identify = self.selected_firmware.get("identifier", "")
            self.firmware_stats_label.setText(f"已选择: {device_identify}")
            self.update_confirm_button()

    def update_page_controls(self):
        """更新翻页控件状态"""
        self.page_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)

    def on_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.query_firmware(self.current_page)

    def on_next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.query_firmware(self.current_page)

    def update_confirm_button(self):
        """更新确认按钮状态"""
        self.confirm_btn.setEnabled(self.has_single_model and self.selected_firmware is not None)

    def on_confirm(self):
        """确认升级"""
        if not self.has_single_model:
            if self.parent_window:
                self.parent_window.show_error("所选设备型号不一致，无法进行批量升级")
            return

        if not self.selected_firmware:
            if self.parent_window:
                self.parent_window.show_warning("请先选择固件")
            return

        if not self.start_background_batch_upgrade():
            return

        self.accept()

    def start_background_batch_upgrade(self):
        """在父页面线程管理器中启动后台批量升级任务。"""
        device_identify = self.selected_firmware.get("identifier", "")
        file_url = self.selected_firmware.get("download_url", "")

        if not file_url:
            if self.parent_window:
                self.parent_window.show_error("固件下载链接为空，无法升级")
            return False

        owner_thread_mgr = getattr(self.parent_window, "thread_mgr", None) or self.thread_mgr
        thread_name = f"batch_upgrade_{int(datetime.now().timestamp() * 1000)}"
        stats = {"success": 0, "offline": 0, "wake_failed": 0, "failed": 0}

        if self.parent_window:
            self.parent_window.show_progress(f"已在后台开始批量升级，共 {len(self.devices)} 台设备...")

        thread = BatchUpgradeThread(
            [(sn, dev_id) for sn, dev_id, _, _ in self.devices],
            device_identify,
            file_url,
            device_query=self.device_query,
            max_workers=self.thread_count,
        )

        def on_upgrade_result(_sn, status, _message, result_stats=stats):
            if status not in result_stats:
                status = "failed"
            result_stats[status] += 1

        def on_upgrade_complete(result_stats=stats, parent=self.parent_window):
            if not parent:
                return

            success_count = result_stats.get("success", 0)
            offline_count = result_stats.get("offline", 0)
            wake_failed_count = result_stats.get("wake_failed", 0)
            failed_count = result_stats.get("failed", 0)

            if success_count > 0:
                parent.show_success(
                    f"升级命令下发完成：成功 {success_count} 台，离线 {offline_count} 台，唤醒失败 {wake_failed_count} 台，失败 {failed_count} 台"
                )
                return

            if offline_count == 0 and wake_failed_count > 0 and failed_count == 0:
                parent.show_error(f"设备离线且唤醒失败：共 {wake_failed_count} 台")
                return

            if offline_count > 0 and wake_failed_count == 0 and failed_count == 0:
                parent.show_error("设备离线，操作失败")
                return

            parent.show_error(
                f"升级下发失败：离线 {offline_count} 台，唤醒失败 {wake_failed_count} 台，失败 {failed_count} 台"
            )

        thread.single_result.connect(on_upgrade_result)
        thread.all_done.connect(on_upgrade_complete)
        if self.parent_window:
            thread.progress.connect(lambda msg, parent=self.parent_window: parent.show_progress(msg))
        thread.finished.connect(lambda: thread.deleteLater())
        owner_thread_mgr.add(thread_name, thread)
        thread.start()
        return True

    def restore_buttons(self):
        """恢复按钮状态"""
        self.batch_wake_btn.setEnabled(True)
        self.refresh_status_btn.setEnabled(True)
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
        for label in self._info_labels:
            self._apply_info_style(label)

        if hasattr(self, "device_stats_label"):
            self.device_stats_label.setStyleSheet(
                f"color: {t('status_info')}; font-size: 13px; font-weight: 600; border: none;"
            )
        if hasattr(self, "page_label"):
            self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")
        if hasattr(self, "firmware_stats_label"):
            self.firmware_stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")
        if hasattr(self, "batch_wake_btn"):
            self._apply_secondary_button_style(self.batch_wake_btn)
        if hasattr(self, "refresh_status_btn"):
            self._apply_secondary_button_style(self.refresh_status_btn)
        if hasattr(self, "prev_page_btn"):
            self._apply_secondary_button_style(self.prev_page_btn)
        if hasattr(self, "next_page_btn"):
            self._apply_secondary_button_style(self.next_page_btn)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
        if hasattr(self, "publisher_combo"):
            self._apply_combo_style(self.publisher_combo)
        if hasattr(self, "audit_combo"):
            self._apply_combo_style(self.audit_combo)
        if hasattr(self, "identifier_input") and self.has_single_model:
            self._apply_read_only_line_edit_style(self.identifier_input)
        if hasattr(self, "device_table"):
            self._apply_table_style(self.device_table)
            self._apply_device_status_colors()
        if hasattr(self, "firmware_table"):
            self._apply_table_style(self.firmware_table)
            self._apply_audit_result_colors()
