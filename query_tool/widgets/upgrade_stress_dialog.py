from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
    QSizePolicy,
)

from .adaptive_dialog import AdaptiveDialog
from .batch_upgrade_dialog import FirmwareQueryThread
from .custom_widgets import ClickableLineEdit, set_dark_title_bar
from query_tool.utils import StyleManager, get_account_config
from query_tool.utils.internal_launch import build_internal_command
from query_tool.utils.task_center import TASK_LIST_LIMIT, count_all_tasks, create_task, ensure_unique_task_name
from query_tool.utils.theme_manager import t


class NoWheelComboBox(QComboBox):
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

        self.init_ui()
        if not self.has_single_model:
            self.task_name_input.setText(ensure_unique_task_name("升级压测"))
        if self.has_single_model:
            self.task_name_input.setText(self._build_default_task_name())
            self.identifier_input.setText(self.device_model)
            self.identifier_input.setReadOnly(True)
            self.identifier_input.setStyleSheet(StyleManager.get_READONLY_INPUT())
            self.query_firmware()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        QTimer.singleShot(0, self._fit_dialog_height_to_contents)

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

        device_group = QGroupBox("设备列表")
        device_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        device_layout = QVBoxLayout(device_group)
        device_layout.setContentsMargins(12, 16, 12, 12)
        device_layout.setSpacing(8)

        device_tip = QLabel(f"已选择 {len(self.devices)} 台设备，型号: {self.device_model or '混合型号'}")
        device_tip.setStyleSheet(f"color: {t('status_info')}; font-size: 13px;")
        device_layout.addWidget(device_tip)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "ID", "型号"])
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(QTableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        row_height = 30
        header_height = 30
        StyleManager.apply_to_widget(self.device_table, "TABLE")
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
        device_group.setFixedHeight(device_group.sizeHint().height())
        layout.addWidget(device_group)

        config_group = QGroupBox("任务配置")
        config_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(12, 16, 12, 12)
        config_layout.setSpacing(8)

        mode_frame = QFrame()
        mode_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(8, 8, 8, 8)
        mode_layout.setSpacing(12)

        self.single_mode_radio = QRadioButton("循环自升")
        self.dual_mode_radio = QRadioButton("双版本互升")
        self.single_mode_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.single_mode_radio)
        self.mode_group.addButton(self.dual_mode_radio)
        self.single_mode_radio.toggled.connect(self.on_mode_changed)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(0, 24 * 60 * 60)
        self.interval_spin.setValue(120)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setFixedWidth(110)

        self.total_cycles_spin = QSpinBox()
        self.total_cycles_spin.setRange(1, 100000)
        self.total_cycles_spin.setValue(5)
        self.total_cycles_spin.setFixedWidth(110)

        self.task_name_input = QLineEdit()

        interval_label = self._create_plain_label("升级间隔:")
        cycles_label = self._create_plain_label("升级轮次:")
        task_name_label = self._create_plain_label("任务名称:")

        mode_layout.addWidget(self.single_mode_radio)
        mode_layout.addWidget(self.dual_mode_radio)
        mode_layout.addSpacing(10)
        mode_layout.addWidget(interval_label)
        mode_layout.addWidget(self.interval_spin)
        mode_layout.addWidget(cycles_label)
        mode_layout.addWidget(self.total_cycles_spin)
        mode_layout.addWidget(task_name_label)
        mode_layout.addWidget(self.task_name_input, 1)
        config_layout.addWidget(mode_frame)

        result_frame = QFrame()
        result_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        result_layout = QHBoxLayout(result_frame)
        result_layout.setContentsMargins(8, 8, 8, 8)
        result_layout.setSpacing(10)

        self.result_dir_input = ClickableLineEdit()
        self.result_dir_input.setReadOnly(True)
        self.result_dir_input.setText(str((Path.home() / "Desktop").resolve()))
        self.result_dir_input.setStyleSheet(StyleManager.get_READONLY_INPUT())

        browse_btn = QPushButton("选择目录")
        browse_btn.setIcon(QIcon(":/icons/common/dir.png"))
        browse_btn.setIconSize(QSize(16, 16))
        browse_btn.setFixedSize(100, 28)
        browse_btn.clicked.connect(self.on_browse_result_dir)

        result_layout.addWidget(self._create_plain_label("结果目录:"))
        result_layout.addWidget(self.result_dir_input, 1)
        result_layout.addWidget(browse_btn)
        config_layout.addWidget(result_frame)
        config_group.setFixedHeight(config_group.sizeHint().height())
        layout.addWidget(config_group)

        query_group = QGroupBox("固件查询")
        query_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        query_layout = QVBoxLayout(query_group)
        query_layout.setContentsMargins(12, 16, 12, 12)
        query_layout.setSpacing(8)

        query_frame = QFrame()
        query_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        query_frame_layout = QHBoxLayout(query_frame)
        query_frame_layout.setContentsMargins(8, 8, 8, 8)
        query_frame_layout.setSpacing(10)

        self.publisher_combo = NoWheelComboBox()
        self.publisher_combo.addItem("当前登录用户", "cur")
        self.publisher_combo.addItem("全部", "all")
        self.publisher_combo.setFixedHeight(28)

        self.audit_combo = NoWheelComboBox()
        self.audit_combo.addItem("全部", "")
        self.audit_combo.addItem("无需审核", "1")
        self.audit_combo.addItem("待审核", "2")
        self.audit_combo.addItem("审核通过", "3")
        self.audit_combo.addItem("审核不通过", "4")
        self.audit_combo.setFixedHeight(28)
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("输入固件标识...")
        self.identifier_input.setFixedHeight(28)

        self.query_btn = QPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedSize(90, 28)
        self.query_btn.clicked.connect(self.query_firmware)

        query_frame_layout.addWidget(self._create_plain_label("发布人员:"))
        query_frame_layout.addWidget(self.publisher_combo, 1)
        query_frame_layout.addWidget(self._create_plain_label("审核状态:"))
        query_frame_layout.addWidget(self.audit_combo, 1)
        query_frame_layout.addWidget(self._create_plain_label("固件标识:"))
        query_frame_layout.addWidget(self.identifier_input, 2)
        query_frame_layout.addWidget(self.query_btn)
        query_layout.addWidget(query_frame)
        query_group.setFixedHeight(query_group.sizeHint().height())
        layout.addWidget(query_group)

        list_group = QGroupBox("固件列表")
        list_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(12, 16, 12, 12)
        list_layout.setSpacing(8)

        self.firmware_table = QTableWidget()
        self.firmware_table.setColumnCount(6)
        self.firmware_table.setHorizontalHeaderLabels(
            ["选择", "固件标识", "审核结果", "开始时间", "结束时间", "发布备注"]
        )
        self.firmware_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.firmware_table.setSelectionMode(QTableWidget.NoSelection)
        self.firmware_table.setFocusPolicy(Qt.StrongFocus)
        firmware_row_height = 30
        firmware_header_height = 30
        firmware_visible_rows = 5
        firmware_table_height = firmware_header_height + (firmware_row_height * firmware_visible_rows) + 10
        self.firmware_table.setMinimumHeight(firmware_table_height)
        self.firmware_table.setMaximumHeight(firmware_table_height)
        self.firmware_table.setWordWrap(True)
        StyleManager.apply_to_widget(self.firmware_table, "TABLE")
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
        self.firmware_table.setTextElideMode(Qt.ElideRight)
        self.firmware_table.cellClicked.connect(self.on_table_cell_clicked)
        list_layout.addWidget(self.firmware_table)

        bottom_layout = QHBoxLayout()
        self.prev_page_btn = QPushButton()
        self.prev_page_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_page_btn.setIconSize(QSize(20, 20))
        self.prev_page_btn.setFixedSize(80, 28)
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.on_prev_page)

        self.page_label = QLabel("第 1 / 1 页")
        self.page_label.setFixedWidth(100)
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_page_btn = QPushButton()
        self.next_page_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_page_btn.setIconSize(QSize(20, 20))
        self.next_page_btn.setFixedSize(80, 28)
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.on_next_page)

        self.selected_label = QLabel("未选择固件")
        self.selected_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px;")
        self.selected_label.setMinimumWidth(220)

        bottom_layout.addWidget(self.prev_page_btn)
        bottom_layout.addWidget(self.page_label)
        bottom_layout.addWidget(self.next_page_btn)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.selected_label)
        list_layout.addLayout(bottom_layout)
        list_group.setFixedHeight(list_group.sizeHint().height())
        layout.addWidget(list_group)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.confirm_btn = QPushButton()
        self.confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.confirm_btn.setIconSize(QSize(20, 20))
        self.confirm_btn.setFixedSize(60, 32)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.on_confirm)

        cancel_btn = QPushButton()
        cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        cancel_btn.setIconSize(QSize(20, 20))
        cancel_btn.setFixedSize(60, 32)
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(cancel_btn)
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

    def _create_plain_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("border: none;")
        return label

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
        if widget is None:
            return None
        return widget.findChild(QCheckBox)

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
            checkbox = QCheckBox()
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
            from PyQt5.QtGui import QColor
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
        selected = [self.firmware_list[row].get("identifier", "") for row in self.selected_rows if row < len(self.firmware_list)]
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
