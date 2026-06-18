from __future__ import annotations

import subprocess
from pathlib import Path

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .adaptive_dialog import AdaptiveDialog
from .batch_upgrade_dialog import FirmwareQueryThread
from .custom_widgets import ClickableLineEdit, set_dark_title_bar
from query_tool.ui import (
    BodyLabel,
    CheckBox,
    ComboBox,
    ElevatedCardWidget,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    RadioButton,
    SpinBox,
    TableWidget,
)
from query_tool.utils import StyleManager, get_account_config
from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.task_center import TASK_LIST_LIMIT, count_all_tasks, create_task, ensure_unique_task_name
from query_tool.utils.theme_manager import t, theme_manager


class NoWheelComboBox(ComboBox):
    """Disable mouse wheel selection changes."""

    def wheelEvent(self, event):
        event.ignore()


class UpgradeStressDialog(AdaptiveDialog):
    """Configure and start firmware upgrade stress tasks."""

    def __init__(self, devices, thread_count, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.thread_count = thread_count
        self.parent_window = parent

        self.firmware_list = []
        self.selected_rows: list[int] = []
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self.query_thread = None

        models = sorted({device[3] for device in devices if len(device) > 3})
        self.device_model = models[0] if len(models) == 1 else ""
        self.has_single_model = len(models) == 1

        self._card_title_labels = []
        self._caption_labels = []
        self._info_labels = []

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()
        if not self.has_single_model:
            self.task_name_input.setText(ensure_unique_task_name("升级压测"))
        if self.has_single_model:
            self.task_name_input.setText(self._build_default_task_name())
            self.identifier_input.setText(self.device_model)
            self.identifier_input.setReadOnly(True)
            self._apply_read_only_line_edit_style(self.identifier_input)
            self.query_firmware()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        QTimer.singleShot(0, self._fit_dialog_height_to_contents)

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

    def _apply_spin_box_style(self, widget):
        if not QFLUENT_WIDGETS_AVAILABLE:
            widget.setStyleSheet(
                f"""
                QSpinBox {{
                    background-color: {t('bg_light')};
                    color: {t('text_primary')};
                    border: 1px solid {t('border')};
                    border-radius: 3px;
                    padding: 4px;
                }}
                QSpinBox:disabled {{
                    background-color: {t('bg_dark')};
                    color: {t('text_disabled')};
                    border: 1px solid {t('border_dark')};
                }}
                """
            )

    def _apply_table_style(self, table):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(table, "TABLE")

    def _apply_audit_result_colors(self):
        audit_colors = {
            "无需审核": t("text_hint"),
            "待审核": t("status_pending"),
            "审核通过": t("status_online"),
            "审核不通过": t("status_offline"),
        }
        for row in range(self.firmware_table.rowCount()):
            item = self.firmware_table.item(row, 2)
            if item is None:
                continue
            item.setData(Qt.ForegroundRole, QColor(audit_colors.get(item.text(), t("text_hint"))))

    @staticmethod
    def _find_checkbox(widget):
        if widget is None:
            return None
        checkbox = widget.findChild(CheckBox)
        if checkbox is not None:
            return checkbox
        return widget.findChild(QCheckBox)

    def init_ui(self):
        self.setWindowTitle("升级压测")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (980, 880),
            min_size=(760, 420),
            scrollable=True,
            layout_margins=(18, 18, 18, 18),
            spacing=12,
        )

        device_card, device_layout = self._create_card_section("设备列表")
        self.device_tip = self._info_label(
            f"已选择 {len(self.devices)} 台设备，型号: {self.device_model or '混合型号'}"
        )
        device_layout.addWidget(self.device_tip)

        self.device_table = TableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "ID", "型号"])
        self.device_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(TableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        self._apply_table_style(self.device_table)

        row_height = 30
        header_height = 30
        header = self.device_table.horizontalHeader()
        header.setFixedHeight(header_height)
        self.device_table.verticalHeader().setDefaultSectionSize(row_height)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.device_table.setColumnWidth(2, 120)
        self.device_table.setColumnWidth(3, 120)
        self.device_table.setRowCount(len(self.devices))
        for row, (sn, dev_id, device_name, model) in enumerate(self.devices):
            self.device_table.setItem(row, 0, QTableWidgetItem(device_name))
            self.device_table.setItem(row, 1, QTableWidgetItem(sn))
            self.device_table.setItem(row, 2, QTableWidgetItem(str(dev_id)))
            self.device_table.setItem(row, 3, QTableWidgetItem(model))
            self.device_table.setRowHeight(row, row_height)
        visible_rows = max(1, min(3, len(self.devices)))
        table_frame = self.device_table.frameWidth() * 2
        visible_table_height = header_height + (row_height * visible_rows) + table_frame + 2
        self.device_table.setFixedHeight(visible_table_height)
        device_layout.addWidget(self.device_table)
        layout.addWidget(device_card)

        config_card, config_layout = self._create_card_section("任务配置")
        if not self.has_single_model:
            self.model_hint_label = self._info_label("当前设备型号不一致，无法创建升级压测任务。")
            config_layout.addWidget(self.model_hint_label)

        mode_row = QWidget()
        mode_row_layout = QHBoxLayout(mode_row)
        mode_row_layout.setContentsMargins(0, 0, 0, 0)
        mode_row_layout.setSpacing(10)

        self.single_mode_radio = RadioButton("循环自升")
        self.dual_mode_radio = RadioButton("双版本互升")
        self.single_mode_radio.setChecked(True)
        self.single_mode_radio.toggled.connect(self.on_mode_changed)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.single_mode_radio)
        self.mode_group.addButton(self.dual_mode_radio)

        self.interval_label = self._caption_label("升级间隔:", width=68)
        self.interval_spin = SpinBox()
        self.interval_spin.setRange(0, 24 * 60 * 60)
        self.interval_spin.setValue(120)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setFixedWidth(116)
        self._apply_spin_box_style(self.interval_spin)

        self.cycles_label = self._caption_label("升级轮次:", width=68)
        self.total_cycles_spin = SpinBox()
        self.total_cycles_spin.setRange(1, 100000)
        self.total_cycles_spin.setValue(5)
        self.total_cycles_spin.setFixedWidth(116)
        self._apply_spin_box_style(self.total_cycles_spin)

        self.task_name_label = self._caption_label("任务名称:", width=68)
        self.task_name_input = LineEdit()
        self.task_name_input.setPlaceholderText("输入任务名称...")

        mode_row_layout.addWidget(self.single_mode_radio)
        mode_row_layout.addWidget(self.dual_mode_radio)
        mode_row_layout.addSpacing(10)
        mode_row_layout.addWidget(self.interval_label)
        mode_row_layout.addWidget(self.interval_spin)
        mode_row_layout.addWidget(self.cycles_label)
        mode_row_layout.addWidget(self.total_cycles_spin)
        mode_row_layout.addWidget(self.task_name_label)
        mode_row_layout.addWidget(self.task_name_input, 1)
        config_layout.addWidget(mode_row)

        result_row = QWidget()
        result_row_layout = QHBoxLayout(result_row)
        result_row_layout.setContentsMargins(0, 0, 0, 0)
        result_row_layout.setSpacing(10)

        self.result_dir_label = self._caption_label("结果目录:", width=68)
        self.result_dir_input = ClickableLineEdit()
        self.result_dir_input.setReadOnly(True)
        self.result_dir_input.setText(str((Path.home() / "Desktop").resolve()))
        self._apply_read_only_line_edit_style(self.result_dir_input)

        self.browse_btn = PushButton("选择目录")
        self.browse_btn.setIcon(QIcon(":/icons/common/dir.png"))
        self.browse_btn.setIconSize(QSize(16, 16))
        self.browse_btn.setFixedSize(104, 32)
        self.browse_btn.clicked.connect(self.on_browse_result_dir)
        self._apply_secondary_button_style(self.browse_btn)

        result_row_layout.addWidget(self.result_dir_label)
        result_row_layout.addWidget(self.result_dir_input, 1)
        result_row_layout.addWidget(self.browse_btn)
        config_layout.addWidget(result_row)
        layout.addWidget(config_card)

        query_card, query_layout = self._create_card_section("固件查询")

        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(10)

        self.publisher_label = self._caption_label("发布人员:", width=70)
        self.publisher_combo = NoWheelComboBox()
        self.publisher_combo.addItem("当前登录用户", "cur")
        self.publisher_combo.addItem("全部", "all")
        self.publisher_combo.setFixedHeight(32)
        self._apply_combo_style(self.publisher_combo)

        self.audit_label = self._caption_label("审核状态:", width=70)
        self.audit_combo = NoWheelComboBox()
        self.audit_combo.addItem("全部", "")
        self.audit_combo.addItem("无需审核", "1")
        self.audit_combo.addItem("待审核", "2")
        self.audit_combo.addItem("审核通过", "3")
        self.audit_combo.addItem("审核不通过", "4")
        self.audit_combo.setFixedHeight(32)
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

        self.query_btn = PrimaryPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedSize(88, 32)
        self.query_btn.clicked.connect(self.query_firmware)

        row2_layout.addWidget(self.identifier_label)
        row2_layout.addWidget(self.identifier_input, 1)
        row2_layout.addStretch()
        row2_layout.addWidget(self.query_btn)
        query_layout.addWidget(row2)
        layout.addWidget(query_card)

        list_card, list_layout = self._create_card_section("固件列表")
        self.firmware_table = TableWidget()
        self.firmware_table.setColumnCount(6)
        self.firmware_table.setHorizontalHeaderLabels(
            ["选择", "固件标识", "审核结果", "开始时间", "结束时间", "发布备注"]
        )
        self.firmware_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.firmware_table.setSelectionMode(TableWidget.NoSelection)
        self.firmware_table.setFocusPolicy(Qt.StrongFocus)
        self.firmware_table.setWordWrap(True)
        self.firmware_table.setTextElideMode(Qt.ElideRight)
        self.firmware_table.cellClicked.connect(self.on_table_cell_clicked)
        self._apply_table_style(self.firmware_table)

        firmware_row_height = 30
        firmware_header_height = 30
        firmware_visible_rows = 5
        firmware_table_height = firmware_header_height + (firmware_row_height * firmware_visible_rows) + 10
        self.firmware_table.setMinimumHeight(firmware_table_height)
        self.firmware_table.setMaximumHeight(firmware_table_height)

        table_header = self.firmware_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.Fixed)
        table_header.setSectionResizeMode(1, QHeaderView.Interactive)
        table_header.setSectionResizeMode(2, QHeaderView.Fixed)
        table_header.setSectionResizeMode(3, QHeaderView.Fixed)
        table_header.setSectionResizeMode(4, QHeaderView.Fixed)
        table_header.setSectionResizeMode(5, QHeaderView.Stretch)
        self.firmware_table.setColumnWidth(0, 50)
        self.firmware_table.setColumnWidth(1, 280)
        self.firmware_table.setColumnWidth(2, 90)
        self.firmware_table.setColumnWidth(3, 90)
        self.firmware_table.setColumnWidth(4, 90)
        list_layout.addWidget(self.firmware_table)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)

        self.prev_page_btn = PushButton("上一页")
        self.prev_page_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_page_btn.setIconSize(QSize(18, 18))
        self.prev_page_btn.setFixedSize(92, 32)
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.on_prev_page)
        self._apply_secondary_button_style(self.prev_page_btn)

        self.page_label = BodyLabel("第 1 / 1 页")
        self.page_label.setFixedWidth(100)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")

        self.next_page_btn = PushButton("下一页")
        self.next_page_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_page_btn.setIconSize(QSize(18, 18))
        self.next_page_btn.setLayoutDirection(Qt.RightToLeft)
        self.next_page_btn.setFixedSize(92, 32)
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.on_next_page)
        self._apply_secondary_button_style(self.next_page_btn)

        self.selected_label = BodyLabel("未选择固件")
        self.selected_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px; border: none;")
        self.selected_label.setMinimumWidth(260)

        bottom_layout.addWidget(self.prev_page_btn)
        bottom_layout.addWidget(self.page_label)
        bottom_layout.addWidget(self.next_page_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.selected_label)
        list_layout.addLayout(bottom_layout)
        layout.addWidget(list_card)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()

        self.confirm_btn = PrimaryPushButton("启动任务")
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

        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        QTimer.singleShot(0, self._fit_dialog_height_to_contents)

    def _fit_dialog_height_to_contents(self):
        if self._adaptive_scroll_area is None or self._adaptive_content_widget is None:
            return

        content_height = self._adaptive_content_widget.layout().sizeHint().height()
        viewport_height = self._adaptive_scroll_area.viewport().height()
        container_extra = self.height() - viewport_height
        target_height = min(self.maximumHeight(), max(self.minimumHeight(), content_height + container_extra))
        if target_height != self.height():
            self.resize(self.width(), target_height)

    def on_browse_result_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择升级压测结果目录",
            self.result_dir_input.text().strip() or str(Path.home()),
        )
        if directory:
            self.result_dir_input.setText(directory)

    def _build_default_task_name(self) -> str:
        model_name = self.device_model or "升级压测"
        return ensure_unique_task_name(f"{model_name}-升级压测")

    def on_mode_changed(self):
        self._enforce_selection_limit()
        self.update_selected_summary()
        self.update_confirm_button()

    def _selected_limit(self) -> int:
        return 1 if self.single_mode_radio.isChecked() else 2

    def _enforce_selection_limit(self):
        limit = self._selected_limit()
        if len(self.selected_rows) <= limit:
            return
        for row in list(self.selected_rows)[limit:]:
            checkbox = self._get_checkbox(row)
            if checkbox is not None:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
        self.selected_rows = self.selected_rows[:limit]

    def _get_checkbox(self, row: int):
        widget = self.firmware_table.cellWidget(row, 0)
        return self._find_checkbox(widget)

    def query_firmware(self, page=None):
        if not self.has_single_model:
            if self.parent_window:
                self.parent_window.show_error("所选设备型号不一致，无法配置升级压测")
            return
        if page is None:
            page = self.current_page
        self.current_page = page

        self.query_btn.setEnabled(False)
        thread = FirmwareQueryThread(
            create_user=self.publisher_combo.currentData(),
            device_identify=self.identifier_input.text().strip(),
            audit_result=self.audit_combo.currentData(),
            page=self.current_page,
            per_page=100,
        )
        self.query_thread = thread
        thread.finished_signal.connect(self.on_firmware_query_finished)
        thread.error_signal.connect(self.on_firmware_query_error)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def on_firmware_query_finished(self, firmware_list, total_count, total_pages):
        self.query_btn.setEnabled(True)
        self.firmware_list = firmware_list
        self.total_count = total_count
        self.total_pages = total_pages
        self.selected_rows = [row for row in self.selected_rows if row < len(self.firmware_list)]
        self.update_firmware_table()
        self.update_page_controls()
        self.update_selected_summary()
        self.update_confirm_button()
        if self.parent_window:
            self.parent_window.show_success(f"查询到 {total_count} 条固件数据")

    def on_firmware_query_error(self, message):
        self.query_btn.setEnabled(True)
        if self.parent_window:
            self.parent_window.show_error(f"固件查询失败: {message}")

    def update_firmware_table(self):
        self.firmware_table.setRowCount(len(self.firmware_list))
        audit_colors = {
            "无需审核": t("text_hint"),
            "待审核": t("status_pending"),
            "审核通过": t("status_online"),
            "审核不通过": t("status_offline"),
        }
        for row, firmware in enumerate(self.firmware_list):
            checkbox = CheckBox()
            checkbox.setChecked(row in self.selected_rows)
            checkbox.stateChanged.connect(lambda state, r=row: self.on_checkbox_changed(r, state))
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.addWidget(checkbox)
            self.firmware_table.setCellWidget(row, 0, checkbox_widget)

            identifier_item = QTableWidgetItem(firmware.get("identifier", ""))
            self.firmware_table.setItem(row, 1, identifier_item)

            audit_result = firmware.get("audit_result", "")
            audit_item = QTableWidgetItem(audit_result)
            audit_item.setData(Qt.ForegroundRole, QColor(audit_colors.get(audit_result, t("text_hint"))))
            audit_item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 2, audit_item)

            start_item = QTableWidgetItem(firmware.get("start_time", ""))
            start_item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 3, start_item)

            end_item = QTableWidgetItem(firmware.get("end_time", ""))
            end_item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 4, end_item)

            remark_item = QTableWidgetItem(firmware.get("remark", ""))
            remark_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.firmware_table.setItem(row, 5, remark_item)

        self.firmware_table.resizeRowsToContents()

    def on_checkbox_changed(self, row, state):
        checked = state == Qt.Checked
        if checked and row not in self.selected_rows:
            self.selected_rows.append(row)
        if not checked and row in self.selected_rows:
            self.selected_rows.remove(row)

        limit = self._selected_limit()
        if len(self.selected_rows) > limit:
            row_to_remove = self.selected_rows.pop(0)
            checkbox = self._get_checkbox(row_to_remove)
            if checkbox is not None:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)

        self.update_selected_summary()
        self.update_confirm_button()

    def on_table_cell_clicked(self, row, column):
        if column == 0:
            return
        checkbox = self._get_checkbox(row)
        if checkbox is not None:
            checkbox.setChecked(not checkbox.isChecked())

    def update_selected_summary(self):
        if not self.selected_rows:
            self.selected_label.setText("未选择固件")
            return
        selected = [
            self.firmware_list[row].get("identifier", "")
            for row in self.selected_rows
            if row < len(self.firmware_list)
        ]
        mode_text = "循环自升" if self.single_mode_radio.isChecked() else "互升"
        self.selected_label.setText(f"{mode_text}已选: {' | '.join(selected)}")

    def update_page_controls(self):
        self.page_label.setText(f"第 {self.current_page} / {self.total_pages} 页")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)

    def on_prev_page(self):
        if self.current_page > 1:
            self.query_firmware(self.current_page - 1)

    def on_next_page(self):
        if self.current_page < self.total_pages:
            self.query_firmware(self.current_page + 1)

    def update_confirm_button(self):
        required = 1 if self.single_mode_radio.isChecked() else 2
        self.confirm_btn.setEnabled(self.has_single_model and len(self.selected_rows) == required)

    def _selected_firmwares(self):
        firmwares = []
        for row in self.selected_rows:
            if row < len(self.firmware_list):
                firmware = self.firmware_list[row]
                firmwares.append(
                    {
                        "identifier": firmware.get("identifier", ""),
                        "download_url": firmware.get("download_url", ""),
                        "id": firmware.get("id", ""),
                    }
                )
        return firmwares

    def on_confirm(self):
        if not self.has_single_model:
            if self.parent_window:
                self.parent_window.show_error("所选设备型号不一致，无法配置升级压测")
            return

        selected_firmwares = self._selected_firmwares()
        required = 1 if self.single_mode_radio.isChecked() else 2
        if len(selected_firmwares) != required:
            if self.parent_window:
                self.parent_window.show_warning("请按当前模式选择正确数量的固件")
            return

        for firmware in selected_firmwares:
            if not firmware.get("download_url"):
                if self.parent_window:
                    self.parent_window.show_error("存在固件下载链接为空，无法启动任务")
                return

        result_root_dir = self.result_dir_input.text().strip()
        if not result_root_dir:
            if self.parent_window:
                self.parent_window.show_warning("请选择结果保存目录")
            return

        env, username, password = get_account_config()
        if not username or not password:
            if self.parent_window:
                self.parent_window.show_error("运维账号未配置，无法启动升级压测")
            return
        if count_all_tasks() >= TASK_LIST_LIMIT:
            if self.parent_window:
                self.parent_window.show_warning("任务列表已满，需要删除后再继续添加")
            return

        task_name = ensure_unique_task_name(
            self.task_name_input.text().strip() or self._build_default_task_name()
        )
        self.task_name_input.setText(task_name)
        try:
            task_meta = create_task(
                "升级压测",
                task_name,
                {
                    "mode": "single" if self.single_mode_radio.isChecked() else "dual",
                    "interval_seconds": self.interval_spin.value(),
                    "total_cycles": self.total_cycles_spin.value(),
                    "max_workers": self.thread_count,
                    "env": env,
                    "username": username,
                    "password": password,
                    "devices": [
                        {
                            "sn": sn,
                            "dev_id": str(dev_id),
                            "device_name": device_name,
                            "model": model,
                        }
                        for sn, dev_id, device_name, model in self.devices
                    ],
                    "firmwares": selected_firmwares,
                },
                result_root_dir,
            )
        except ValueError as exc:
            if self.parent_window:
                self.parent_window.show_warning(str(exc))
            return

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            build_internal_command("--upgrade-stress-runner", task_meta["task_id"]),
            creationflags=creation_flags,
        )

        if self.parent_window:
            self.parent_window.show_success(f"升级压测任务已启动: {task_name}")
            if hasattr(self.parent_window, "refresh_running_task_indicator"):
                self.parent_window.refresh_running_task_indicator()

        self.accept()

    def closeEvent(self, event):
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.quit()
            self.query_thread.wait(1000)
        super().closeEvent(event)

    def refresh_theme(self):
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for label in self._caption_labels:
            self._apply_caption_style(label)
        for label in self._info_labels:
            self._apply_info_style(label)

        if hasattr(self, "publisher_combo"):
            self._apply_combo_style(self.publisher_combo)
        if hasattr(self, "audit_combo"):
            self._apply_combo_style(self.audit_combo)
        if hasattr(self, "identifier_input") and self.identifier_input.isReadOnly():
            self._apply_read_only_line_edit_style(self.identifier_input)
        if hasattr(self, "result_dir_input"):
            self._apply_read_only_line_edit_style(self.result_dir_input)
        if hasattr(self, "interval_spin"):
            self._apply_spin_box_style(self.interval_spin)
        if hasattr(self, "total_cycles_spin"):
            self._apply_spin_box_style(self.total_cycles_spin)
        if hasattr(self, "browse_btn"):
            self._apply_secondary_button_style(self.browse_btn)
        if hasattr(self, "prev_page_btn"):
            self._apply_secondary_button_style(self.prev_page_btn)
        if hasattr(self, "next_page_btn"):
            self._apply_secondary_button_style(self.next_page_btn)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
        if hasattr(self, "page_label"):
            self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")
        if hasattr(self, "selected_label"):
            self.selected_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px; border: none;")
        if hasattr(self, "single_mode_radio"):
            self.single_mode_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, "dual_mode_radio"):
            self.dual_mode_radio.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, "device_table"):
            self._apply_table_style(self.device_table)
        if hasattr(self, "firmware_table"):
            self._apply_table_style(self.firmware_table)
            self._apply_audit_result_colors()
