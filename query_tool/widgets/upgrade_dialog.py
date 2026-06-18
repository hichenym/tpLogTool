"""
设备固件升级对话框
"""
from datetime import datetime

from PyQt5.QtCore import QSize, Qt, QThread, pyqtSignal
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


class StatusQueryThread(QThread):
    """状态查询线程"""

    finished_signal = pyqtSignal(bool, str)  # is_online, message

    def __init__(self, sn, device_query, dev_id=None):
        super().__init__()
        self.sn = sn
        self.device_query = device_query
        self.dev_id = dev_id

    def run(self):
        try:
            from query_tool.utils.device_query import query_device_online_state

            online_state = query_device_online_state(self.sn, self.device_query, dev_id=self.dev_id)
            if online_state is True:
                self.finished_signal.emit(True, "在线")
            elif online_state is False:
                self.finished_signal.emit(False, "离线")
            else:
                self.finished_signal.emit(False, "查询失败")
        except Exception as e:
            self.finished_signal.emit(False, f"查询失败: {str(e)}")


class WakeDeviceThread(QThread):
    """唤醒设备线程"""

    finished_signal = pyqtSignal(bool, str)  # success, message

    def __init__(self, dev_id, sn, device_query):
        super().__init__()
        self.dev_id = dev_id
        self.sn = sn
        self.device_query = device_query

    def run(self):
        try:
            from query_tool.utils import wake_device_smart

            is_online = wake_device_smart(
                self.dev_id,
                self.sn,
                self.device_query,
                max_times=3,
            )
            if is_online:
                self.finished_signal.emit(True, "唤醒成功")
            else:
                self.finished_signal.emit(False, "唤醒失败")
        except Exception as e:
            self.finished_signal.emit(False, f"唤醒出错: {str(e)}")


class FirmwareQueryThread(QThread):
    """固件查询线程"""

    finished_signal = pyqtSignal(list, int, int)  # firmware_list, total_count, total_pages
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


class UpgradeThread(QThread):
    """升级命令发送线程"""

    finished_signal = pyqtSignal(bool, str)  # success, message

    def __init__(self, sn, dev_id, device_identify, file_url, device_query):
        super().__init__()
        self.sn = sn
        self.dev_id = dev_id
        self.device_identify = device_identify
        self.file_url = file_url
        self.device_query = device_query

    def run(self):
        try:
            status, message = prepare_and_send_upgrade(
                self.sn,
                self.dev_id,
                self.device_identify,
                self.file_url,
                device_query=self.device_query,
                max_wake_times=3,
            )
            self.finished_signal.emit(status == "success", message)
        except Exception as e:
            logger.error(f"升级出错: {e}")
            self.finished_signal.emit(False, f"升级出错: {str(e)}")


class UpgradeDialog(AdaptiveDialog):
    """设备固件升级对话框"""

    def __init__(self, sn, dev_id, device_name, model, device_query, parent=None):
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_name = device_name
        self.model = model
        self.device_query = device_query
        self.parent_window = parent

        self.is_online = False
        self.selected_firmware = None

        self.thread_mgr = ThreadManager()
        self.firmware_list = []
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0

        self._card_title_labels = []
        self._caption_labels = []
        self._info_labels = []

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()
        self.query_status()
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

    def _apply_icon_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_combo_style(self, combo):
        if not QFLUENT_WIDGETS_AVAILABLE:
            combo.setStyleSheet(StyleManager.get_COMBOBOX())

    def _apply_read_only_line_edit_style(self, widget):
        if not QFLUENT_WIDGETS_AVAILABLE:
            widget.setStyleSheet(StyleManager.get_READONLY_INPUT())

    def _apply_table_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE and hasattr(self, "firmware_table"):
            StyleManager.apply_to_widget(self.firmware_table, "TABLE")

    def _set_status_state(self, text, color_role):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {t(color_role)}; font-size: 12px; border: none;")

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
        self.setWindowTitle("设备固件升级")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (920, 640),
            min_size=(700, 460),
            scrollable=True,
            layout_margins=(20, 20, 20, 20),
            spacing=14,
        )

        self.info_label = self._info_label(f"设备: {self.device_name}    SN: {self.sn}    型号: {self.model}")
        layout.addWidget(self.info_label)

        status_card, status_layout = self._create_card_section("设备状态")
        status_row = QWidget()
        status_row_layout = QHBoxLayout(status_row)
        status_row_layout.setContentsMargins(0, 0, 0, 0)
        status_row_layout.setSpacing(10)

        self.status_text_label = self._caption_label("在线状态:", width=70)
        self.status_label = BodyLabel("● 查询中...")
        self.status_label.setFixedWidth(90)
        self._set_status_state("● 查询中...", "text_hint")

        self.wake_btn = PushButton("")
        self.wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.wake_btn.setIconSize(QSize(16, 16))
        self.wake_btn.setFixedSize(32, 32)
        self.wake_btn.setEnabled(False)
        self.wake_btn.setToolTip("唤醒设备")
        self.wake_btn.clicked.connect(self.on_wake)
        self._apply_icon_button_style(self.wake_btn)

        self.refresh_btn = PushButton("")
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("刷新状态")
        self.refresh_btn.clicked.connect(self.on_refresh)
        self._apply_icon_button_style(self.refresh_btn)

        status_row_layout.addWidget(self.status_text_label)
        status_row_layout.addWidget(self.status_label)
        status_row_layout.addSpacing(4)
        status_row_layout.addWidget(self.wake_btn)
        status_row_layout.addWidget(self.refresh_btn)
        status_row_layout.addStretch()
        status_layout.addWidget(status_row)
        layout.addWidget(status_card)

        query_card, query_layout = self._create_card_section("固件查询")

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
        self.identifier_input.setText(self.model)
        self.identifier_input.setReadOnly(True)
        self.identifier_input.setFixedHeight(32)
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
        self._apply_table_style()

        header = self.firmware_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.firmware_table.setColumnWidth(0, 56)
        self.firmware_table.setColumnWidth(1, 280)
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

        self.stats_label = BodyLabel("未选择固件")
        self.stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")

        footer_layout.addWidget(self.prev_page_btn)
        footer_layout.addWidget(self.page_label)
        footer_layout.addWidget(self.next_page_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(self.stats_label)
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

    def query_status(self):
        """查询设备在线状态"""
        self._set_status_state("● 查询中...", "text_hint")
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        if self.device_query and not self.device_query.init_error:
            thread = StatusQueryThread(self.sn, self.device_query, self.dev_id)
            thread.finished_signal.connect(self.on_status_query_finished)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("status_query", thread)
            thread.start()
        else:
            self._set_status_state("● 查询失败", "text_hint")

    def on_status_query_finished(self, is_online, message):
        """状态查询完成"""
        self.is_online = is_online

        if is_online:
            self._set_status_state("● 在线", "status_online")
        else:
            self._set_status_state("● 离线", "status_offline")

        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.update_confirm_button()

    def on_refresh(self):
        """刷新状态"""
        self.query_status()

    def on_wake(self):
        """唤醒设备"""
        self._set_status_state("● 唤醒中...", "status_pending")
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)

        thread = WakeDeviceThread(self.dev_id, self.sn, self.device_query)
        thread.finished_signal.connect(self.on_wake_finished)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("wake_device", thread)
        thread.start()

    def on_wake_finished(self, success, message):
        """唤醒完成"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

        if success:
            self.is_online = True
            self._set_status_state("● 在线", "status_online")
        elif self.is_online:
            self._set_status_state("● 在线", "status_online")
        else:
            self._set_status_state("● 离线", "status_offline")

        self.update_confirm_button()

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
            self.stats_label.setText(f"已选择: {device_identify}")
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
            self.stats_label.setText(f"已选择: {device_identify}")
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
        self.confirm_btn.setEnabled(self.selected_firmware is not None)

    def on_confirm(self):
        """确认升级"""
        if not self.selected_firmware:
            if self.parent_window:
                self.parent_window.show_warning("请先选择固件")
            return

        if not self.device_query or not self.device_query.token:
            if self.parent_window:
                self.parent_window.show_error("无法获取访问令牌，操作失败")
            return

        if not self.start_background_upgrade():
            return

        self.accept()

    def start_background_upgrade(self):
        """在父页面线程管理器中启动后台升级任务。"""
        device_identify = self.selected_firmware.get("identifier", "")
        file_url = self.selected_firmware.get("download_url", "")

        if not file_url:
            if self.parent_window:
                self.parent_window.show_error("固件下载链接为空，无法升级")
            return False

        owner_thread_mgr = getattr(self.parent_window, "thread_mgr", None) or self.thread_mgr
        thread_name = f"upgrade_{self.sn}_{int(datetime.now().timestamp() * 1000)}"

        thread = UpgradeThread(
            self.sn,
            self.dev_id,
            device_identify,
            file_url,
            self.device_query,
        )

        if self.parent_window:
            self.parent_window.show_progress(f"已在后台开始升级 {self.sn}...")

        def handle_finished(success, message, sn=self.sn, parent=self.parent_window):
            if not parent:
                return
            if success:
                parent.show_success(f"升级命令已发送: {sn}")
            else:
                parent.show_error(f"升级失败: {message}")

        thread.finished_signal.connect(handle_finished)
        thread.finished.connect(lambda: thread.deleteLater())
        owner_thread_mgr.add(thread_name, thread)
        thread.start()
        return True

    def restore_buttons(self):
        """恢复按钮状态"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

    def refresh_theme(self):
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for label in self._caption_labels:
            self._apply_caption_style(label)
        for label in self._info_labels:
            self._apply_info_style(label)

        if hasattr(self, "page_label"):
            self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")
        if hasattr(self, "stats_label"):
            self.stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")
        if hasattr(self, "publisher_combo"):
            self._apply_combo_style(self.publisher_combo)
        if hasattr(self, "audit_combo"):
            self._apply_combo_style(self.audit_combo)
        if hasattr(self, "identifier_input"):
            self._apply_read_only_line_edit_style(self.identifier_input)
        if hasattr(self, "wake_btn"):
            self._apply_icon_button_style(self.wake_btn)
        if hasattr(self, "refresh_btn"):
            self._apply_icon_button_style(self.refresh_btn)
        if hasattr(self, "prev_page_btn"):
            self._apply_secondary_button_style(self.prev_page_btn)
        if hasattr(self, "next_page_btn"):
            self._apply_secondary_button_style(self.next_page_btn)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
        if hasattr(self, "firmware_table"):
            self._apply_table_style()
            self._apply_audit_result_colors()
        if hasattr(self, "status_label"):
            if self.status_label.text().endswith("在线"):
                self._set_status_state(self.status_label.text(), "status_online")
            elif self.status_label.text().endswith("离线"):
                self._set_status_state(self.status_label.text(), "status_offline")
            elif "唤醒中" in self.status_label.text():
                self._set_status_state(self.status_label.text(), "status_pending")
            else:
                self._set_status_state(self.status_label.text(), "text_hint")
