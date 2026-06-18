"""
批量电池电量数据采集对话框
"""

import csv

from PyQt5.QtCore import QDateTime, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QDateTimeEdit,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from query_tool.ui import (
    BodyLabel,
    ElevatedCardWidget,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    TableWidget,
)
from query_tool.utils import StyleManager
from query_tool.utils.data_collect_api import BatchDataCollectThread
from query_tool.utils.logger import logger
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.widgets.custom_widgets import (
    set_dark_title_bar,
    show_message_box,
    show_question_box,
)


class BatchBatteryCollectDialog(AdaptiveDialog):
    """批量电池电量数据采集对话框"""

    log_message = pyqtSignal(str)

    def __init__(self, devices, thread_count, device_query=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.thread_count = thread_count
        self.device_query = device_query
        self.query_thread = None
        self.all_results = []
        self.device_status = {}
        self.resize_timer = None
        self._card_title_labels = []
        self._caption_labels = []
        self._info_labels = []

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        self.adjust_table_columns()

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
        label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")
        self._caption_labels.append(label)
        return label

    def _info_label(self, text):
        label = BodyLabel(text)
        self._info_labels.append(label)
        self._apply_info_style(label)
        return label

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_table_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.device_table, "TABLE")

    def _apply_progress_bar_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            self.progress_bar.setStyleSheet(
                f"""
                QProgressBar {{
                    border: 1px solid {t('border')};
                    border-radius: 3px;
                    background-color: {t('bg_mid')};
                    text-align: center;
                    color: {t('text_primary')};
                    height: 20px;
                }}
                QProgressBar::chunk {{
                    background-color: {t('status_info')};
                }}
                """
            )

    def _show_warning(self, title, text):
        show_message_box(self, QMessageBox.Warning, title, text)

    @staticmethod
    def _exec_dialog(dialog):
        exec_method = getattr(dialog, "exec", None)
        if callable(exec_method):
            return exec_method()
        return dialog.exec_()

    def init_ui(self):
        self.setWindowTitle("电池电量批量采集")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (920, 720),
            min_size=(700, 520),
            scrollable=True,
            layout_margins=(20, 20, 20, 20),
            spacing=15,
        )

        self.device_count_label = self._info_label(
            f"已选择 {len(self.devices)} 台设备，线程数: {self.thread_count}"
        )
        layout.addWidget(self.device_count_label)

        config_card, config_layout = self._create_card_section("查询配置")

        time_row1 = QWidget()
        time_row1_layout = QHBoxLayout(time_row1)
        time_row1_layout.setContentsMargins(0, 0, 0, 0)
        time_row1_layout.setSpacing(10)

        self.time_range_label = self._caption_label("时间范围:", width=70)

        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        start_dt = QDateTime.currentDateTime().addDays(-6)
        start_dt.setTime(start_dt.time().fromString("00:00:00", "HH:mm:ss"))
        self.start_time_edit.setDateTime(start_dt)

        self.separator_label = BodyLabel("至")
        self.separator_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px; border: none;")
        self.separator_label.setAlignment(Qt.AlignCenter)
        self.separator_label.setFixedWidth(30)

        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        end_dt = QDateTime.currentDateTime()
        end_dt.setTime(end_dt.time().fromString("23:59:59", "HH:mm:ss"))
        self.end_time_edit.setDateTime(end_dt)

        time_row1_layout.addWidget(self.time_range_label)
        time_row1_layout.addWidget(self.start_time_edit, 1)
        time_row1_layout.addWidget(self.separator_label)
        time_row1_layout.addWidget(self.end_time_edit, 1)
        config_layout.addWidget(time_row1)

        time_row2 = QWidget()
        time_row2_layout = QHBoxLayout(time_row2)
        time_row2_layout.setContentsMargins(0, 0, 0, 0)
        time_row2_layout.setSpacing(10)

        self.quick_range_buttons = []
        for days, label in [(1, "最近1天"), (7, "最近7天"), (15, "最近15天"), (30, "最近30天")]:
            btn = PushButton(label)
            btn.clicked.connect(lambda checked=False, d=days: self.on_quick_time_select(d))
            self._apply_secondary_button_style(btn)
            self.quick_range_buttons.append(btn)
            time_row2_layout.addWidget(btn)

        time_row2_layout.addStretch()

        self.query_btn = PrimaryPushButton("开始查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedSize(108, 32)
        self.query_btn.clicked.connect(self.on_query)
        time_row2_layout.addWidget(self.query_btn)

        config_layout.addWidget(time_row2)
        layout.addWidget(config_card)

        progress_card, progress_layout = self._create_card_section("查询进度")

        self.device_table = TableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "记录数"])
        self.device_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(TableWidget.SingleSelection)
        self.device_table.setSelectionBehavior(TableWidget.SelectRows)
        self.device_table.setMinimumHeight(220)
        self._apply_table_style()

        header = self.device_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.device_table.setColumnWidth(0, 300)
        self.device_table.setColumnWidth(1, 200)
        self.device_table.setColumnWidth(2, 150)
        self.device_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.device_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        header.sectionResized.connect(self.on_column_resized)

        self.init_device_table()
        progress_layout.addWidget(self.device_table)

        self.tip_label = BodyLabel("提示: 双击记录数查看单台详情数据")
        self.tip_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px; border: none;")
        progress_layout.addWidget(self.tip_label)

        self.device_table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        self.progress_bar = ProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(len(self.devices))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m (%p%)")
        self._apply_progress_bar_style()
        progress_layout.addWidget(self.progress_bar)

        self.stats_label = BodyLabel("成功: 0 台  失败: 0 台  总记录: 0 条")
        self.stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px; border: none;")
        progress_layout.addWidget(self.stats_label)
        layout.addWidget(progress_card)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.export_btn = PushButton("导出结果")
        self.export_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(108, 34)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.on_export)
        self._apply_secondary_button_style(self.export_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addStretch()

        self.close_btn = PushButton("关闭")
        self.close_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.close_btn.setIconSize(QSize(18, 18))
        self.close_btn.setFixedSize(92, 34)
        self.close_btn.clicked.connect(self.accept)
        self._apply_secondary_button_style(self.close_btn)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_table_columns()

    def on_column_resized(self, logicalIndex):
        from PyQt5.QtCore import QTimer

        if self.resize_timer is not None:
            self.resize_timer.stop()
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self._do_column_resize(logicalIndex))
        self.resize_timer.start(200)

    def _do_column_resize(self, logicalIndex):
        table_width = self.device_table.width()
        if table_width <= 0:
            return
        current_total = sum(self.device_table.columnWidth(col) for col in range(3))
        diff = table_width - current_total
        if diff != 0:
            other_cols = [col for col in range(3) if col != logicalIndex]
            if other_cols:
                for col in other_cols:
                    new_width = max(50, int(self.device_table.columnWidth(col) + diff / len(other_cols)))
                    self.device_table.setColumnWidth(col, new_width)

    def adjust_table_columns(self):
        if not hasattr(self, "device_table"):
            return
        table_width = self.device_table.width()
        if table_width <= 0:
            return
        current_total = sum(self.device_table.columnWidth(col) for col in range(3))
        if current_total != table_width and current_total > 0:
            scale_factor = table_width / current_total
            for col in range(3):
                new_width = max(50, int(self.device_table.columnWidth(col) * scale_factor))
                self.device_table.setColumnWidth(col, new_width)

    def init_device_table(self):
        self.device_table.setRowCount(len(self.devices))
        for row, device in enumerate(self.devices):
            name_item = QTableWidgetItem(device.get("device_name", ""))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            name_item.setData(Qt.UserRole, device)
            self.device_table.setItem(row, 0, name_item)

            sn = device.get("sn", "")
            sn_item = QTableWidgetItem(sn)
            sn_item.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(row, 1, sn_item)

            count_item = QTableWidgetItem("-")
            count_item.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(row, 2, count_item)

            self.device_status[sn] = {"row": row, "status": "waiting", "count": 0}

    def on_cell_double_clicked(self, row, col):
        """双击记录数列弹出该设备的电池电量详情"""
        if col != 2:
            return

        sn_item = self.device_table.item(row, 1)
        if not sn_item:
            return
        sn = sn_item.text()

        device_data = None
        for result in self.all_results:
            if result.get("sn") == sn and result.get("success"):
                device_data = result["data"]
                break

        if not device_data:
            self._emit_log(f"暂无 {sn} 的查询数据，请先执行查询")
            return

        name_item = self.device_table.item(row, 0)
        device_info = name_item.data(Qt.UserRole) if name_item else {}
        device_name = device_info.get("device_name", "") if device_info else ""
        model = device_info.get("model", "") if device_info else ""
        dev_id = device_info.get("dev_id", "") if device_info else ""

        from query_tool.widgets.battery_collect_dialog import BatteryCollectDialog

        dialog = BatteryCollectDialog(
            sn,
            dev_id,
            device_name,
            model,
            device_query=self.device_query,
            parent=self,
            prefill_data=device_data,
        )
        dialog.log_message.connect(self._emit_log)
        self._exec_dialog(dialog)

    def on_quick_time_select(self, days):
        end_time = QDateTime.currentDateTime()
        end_time.setTime(end_time.time().fromString("23:59:59", "HH:mm:ss"))
        start_time = QDateTime.currentDateTime().addDays(-(days - 1))
        start_time.setTime(start_time.time().fromString("00:00:00", "HH:mm:ss"))
        self.start_time_edit.setDateTime(start_time)
        self.end_time_edit.setDateTime(end_time)

    def _emit_log(self, message):
        self.log_message.emit(message)

    def on_query(self):
        start_time = self.start_time_edit.dateTime()
        end_time = self.end_time_edit.dateTime()

        if start_time >= end_time:
            self._show_warning("提示", "开始时间必须早于结束时间")
            return

        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.all_results = []
        self.progress_bar.setValue(0)

        for sn, info in self.device_status.items():
            row = info["row"]
            item = self.device_table.item(row, 2)
            if item:
                item.setText("-")

        if self.device_query and not self.device_query.init_error:
            token = self.device_query.token
            host = self.device_query.host
        else:
            from query_tool.utils.config import get_account_config
            from query_tool.utils.device_query import DeviceQuery

            env, username, password = get_account_config()
            if not username or not password:
                self._show_warning("错误", "未配置账号信息，请先在设置中配置")
                self.query_btn.setEnabled(True)
                self.query_btn.setText("开始查询")
                return
            dq = DeviceQuery(env, username, password)
            if dq.init_error:
                self._show_warning("错误", f"获取认证信息失败: {dq.init_error}")
                self.query_btn.setEnabled(True)
                self.query_btn.setText("开始查询")
                return
            token = dq.token
            host = dq.host

        self._emit_log(f"开始批量查询 {len(self.devices)} 台设备电池电量，线程数: {self.thread_count}")

        self.query_thread = BatchDataCollectThread(
            self.devices,
            "battery",
            start_time.toString("yyyy-MM-dd HH:mm:ss"),
            end_time.toString("yyyy-MM-dd HH:mm:ss"),
            token,
            host,
            self.thread_count,
        )
        self.query_thread.progress.connect(self.on_device_progress)
        self.query_thread.finished.connect(self.on_query_complete)
        self.query_thread.log_message.connect(self._emit_log)
        self.query_thread.start()

    def on_device_progress(self, sn, status, record_count, message):
        if sn not in self.device_status:
            return
        row = self.device_status[sn]["row"]
        if status == "success":
            self.device_table.item(row, 2).setText(f"{record_count}条")
            self.device_status[sn]["status"] = "success"
            self.device_status[sn]["count"] = record_count
            self.progress_bar.setValue(self.progress_bar.value() + 1)
        elif status == "failed":
            self.device_table.item(row, 2).setText("失败")
            self.device_status[sn]["status"] = "failed"
            self.progress_bar.setValue(self.progress_bar.value() + 1)

    def on_query_complete(self, success_count, fail_count, total_records, all_results):
        self.query_btn.setEnabled(True)
        self.query_btn.setText("开始查询")
        self.all_results = all_results
        self.stats_label.setText(f"成功: {success_count} 台  失败: {fail_count} 台  总记录: {total_records} 条")
        if total_records > 0:
            self.export_btn.setEnabled(True)
        self._emit_log(f"批量查询完成: 成功 {success_count} 台，失败 {fail_count} 台，共 {total_records} 条记录")

    def on_export(self):
        if not self.all_results:
            self._emit_log("没有可导出的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出数据",
            f"批量电池电量_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.csv",
            "CSV文件 (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["设备名称", "SN", "型号", "采集时间", "电量(%)"])
                for result in self.all_results:
                    if result["success"]:
                        for item in result["data"]:
                            writer.writerow(
                                [
                                    result.get("device_name", ""),
                                    result.get("sn", ""),
                                    result.get("model", ""),
                                    item.get("time", ""),
                                    item.get("battery", ""),
                                ]
                            )
            import os

            self._emit_log(f"导出成功: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            self._emit_log(f"导出失败: {str(e)}")

    def closeEvent(self, event):
        if self.query_thread and self.query_thread.isRunning():
            reply = show_question_box(self, "确认", "查询正在进行中，确定要关闭吗？")
            if reply == QMessageBox.Yes:
                self.query_thread.stop()
                self.query_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def refresh_theme(self):
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for label in self._caption_labels:
            self._apply_caption_style(label)
        for label in self._info_labels:
            self._apply_info_style(label)

        if hasattr(self, "separator_label"):
            self.separator_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px; border: none;")
        if hasattr(self, "tip_label"):
            self.tip_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px; border: none;")
        if hasattr(self, "stats_label"):
            self.stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px; border: none;")
        if hasattr(self, "device_count_label"):
            self._apply_info_style(self.device_count_label)
        if hasattr(self, "device_table"):
            self._apply_table_style()
        if hasattr(self, "progress_bar"):
            self._apply_progress_bar_style()
        for button in getattr(self, "quick_range_buttons", []):
            self._apply_secondary_button_style(button)
        for attr in ("export_btn", "close_btn"):
            if hasattr(self, attr):
                self._apply_secondary_button_style(getattr(self, attr))
