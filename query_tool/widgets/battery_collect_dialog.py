"""
单设备电池电量数据采集对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QGroupBox, QHeaderView, QMessageBox, QFileDialog,
                             QDateTimeEdit, QWidget)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtGui import QIcon
from query_tool.widgets.custom_widgets import set_dark_title_bar
from query_tool.utils.data_collect_api import DataCollectThread
from query_tool.utils.logger import logger
import csv


class BatteryCollectDialog(QDialog):
    """单设备电池电量数据采集对话框"""

    # 日志信号，发送到主界面左下角
    log_message = pyqtSignal(str)

    def __init__(self, sn, dev_id, device_name, model, device_query=None, parent=None,
                 prefill_data=None):
        """
        Args:
            prefill_data: 预填充数据列表 [{'time': ..., 'battery': ...}, ...]
                          传入时直接展示数据，不需要重新查询
        """
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_name = device_name
        self.model = model
        self.device_query = device_query  # 复用已有的DeviceQuery对象
        self.query_results = prefill_data or []
        self.query_thread = None
        self.resize_timer = None
        self.init_ui()
        # 如果有预填充数据，直接展示
        if prefill_data:
            self.update_result_table()
            self.stats_label.setText(f"共查询到 {len(prefill_data)} 条记录")
            self.export_btn.setEnabled(len(prefill_data) > 0)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        self.adjust_table_columns()

    def init_ui(self):
        self.setWindowTitle("电池电量")
        self.setFixedSize(700, 600)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 设备信息
        info_label = QLabel(f"设备: {self.device_name}    SN: {self.sn}    型号: {self.model}")
        info_label.setStyleSheet("color: #4a9eff; font-size: 13px;")
        layout.addWidget(info_label)

        # 查询配置分组
        config_group = QGroupBox("查询配置")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(15, 20, 15, 15)
        config_layout.setSpacing(12)

        datetime_style = """
            QDateTimeEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
                min-height: 24px;
            }
            QDateTimeEdit:hover { border: 1px solid #6a6a6a; }
            QDateTimeEdit::drop-down {
                border: none;
                background-color: #505050;
                width: 20px;
            }
        """

        # 时间范围行
        time_row1 = QWidget()
        time_row1_layout = QHBoxLayout(time_row1)
        time_row1_layout.setContentsMargins(0, 0, 0, 0)
        time_row1_layout.setSpacing(10)

        time_range_label = QLabel("时间范围:")
        time_range_label.setFixedWidth(70)
        time_range_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")

        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        start_dt = QDateTime.currentDateTime().addDays(-6)
        start_dt.setTime(start_dt.time().fromString("00:00:00", "HH:mm:ss"))
        self.start_time_edit.setDateTime(start_dt)
        self.start_time_edit.setStyleSheet(datetime_style)

        separator_label = QLabel("至")
        separator_label.setStyleSheet("color: #909090; font-size: 12px;")
        separator_label.setAlignment(Qt.AlignCenter)
        separator_label.setFixedWidth(30)

        self.end_time_edit = QDateTimeEdit()
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        end_dt = QDateTime.currentDateTime()
        end_dt.setTime(end_dt.time().fromString("23:59:59", "HH:mm:ss"))
        self.end_time_edit.setDateTime(end_dt)
        self.end_time_edit.setStyleSheet(datetime_style)

        time_row1_layout.addWidget(time_range_label)
        time_row1_layout.addWidget(self.start_time_edit, 1)
        time_row1_layout.addWidget(separator_label)
        time_row1_layout.addWidget(self.end_time_edit, 1)
        config_layout.addWidget(time_row1)

        # 快捷按钮行
        btn_style = """
            QPushButton {
                background-color: #404040; color: #e0e0e0;
                border: 1px solid #555555; border-radius: 3px;
                padding: 4px 12px; min-height: 24px;
            }
            QPushButton:hover { background-color: #4a4a4a; border: 1px solid #6a6a6a; }
            QPushButton:pressed { background-color: #3c3c3c; }
            QPushButton:disabled { background-color: #2b2b2b; color: #606060; border: 1px solid #3c3c3c; }
        """

        time_row2 = QWidget()
        time_row2_layout = QHBoxLayout(time_row2)
        time_row2_layout.setContentsMargins(0, 0, 0, 0)
        time_row2_layout.setSpacing(10)

        for days, label in [(1, "最近1天"), (7, "最近7天"), (15, "最近15天"), (30, "最近30天")]:
            btn = QPushButton(label)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, d=days: self.on_quick_time_select(d))
            time_row2_layout.addWidget(btn)

        time_row2_layout.addStretch()

        self.query_btn = QPushButton("开始查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setFixedSize(100, 28)
        self.query_btn.setStyleSheet(btn_style)
        self.query_btn.clicked.connect(self.on_query)
        time_row2_layout.addWidget(self.query_btn)

        config_layout.addWidget(time_row2)
        layout.addWidget(config_group)

        # 查询结果分组
        result_group = QGroupBox("查询结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(15, 20, 15, 15)
        result_layout.setSpacing(12)

        self.result_table = QTableWidget()
        self.result_table.setColumnCount(2)
        self.result_table.setHorizontalHeaderLabels(["采集时间", "电量(%)"])
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setMinimumHeight(200)

        from query_tool.utils import StyleManager
        StyleManager.apply_to_widget(self.result_table, "TABLE")

        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.result_table.setColumnWidth(0, 400)
        self.result_table.setColumnWidth(1, 200)
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        header.sectionResized.connect(self.on_column_resized)

        result_layout.addWidget(self.result_table)

        bottom_layout = QHBoxLayout()
        self.stats_label = QLabel("共查询到 0 条记录")
        self.stats_label.setStyleSheet("color: #4a9eff; font-size: 12px;")

        self.export_btn = QPushButton("导出结果")
        self.export_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_btn.setFixedSize(100, 28)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(btn_style)
        self.export_btn.clicked.connect(self.on_export)

        bottom_layout.addWidget(self.stats_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.export_btn)
        result_layout.addLayout(bottom_layout)

        layout.addWidget(result_group)

        # 底部关闭按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.close_btn.setFixedSize(80, 32)
        self.close_btn.setStyleSheet(btn_style)
        self.close_btn.clicked.connect(self.accept)
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
        table_width = self.result_table.width()
        if table_width <= 0:
            return
        current_total = sum(self.result_table.columnWidth(col) for col in range(2))
        diff = table_width - current_total
        if diff != 0:
            other_cols = [col for col in range(2) if col != logicalIndex]
            if other_cols:
                for col in other_cols:
                    new_width = max(50, int(self.result_table.columnWidth(col) + diff / len(other_cols)))
                    self.result_table.setColumnWidth(col, new_width)

    def adjust_table_columns(self):
        if not hasattr(self, 'result_table'):
            return
        table_width = self.result_table.width()
        if table_width <= 0:
            return
        current_total = sum(self.result_table.columnWidth(col) for col in range(2))
        if current_total != table_width and current_total > 0:
            scale_factor = table_width / current_total
            for col in range(2):
                new_width = max(50, int(self.result_table.columnWidth(col) * scale_factor))
                self.result_table.setColumnWidth(col, new_width)

    def on_quick_time_select(self, days):
        end_time = QDateTime.currentDateTime()
        end_time.setTime(end_time.time().fromString("23:59:59", "HH:mm:ss"))
        start_time = QDateTime.currentDateTime().addDays(-(days - 1))
        start_time.setTime(start_time.time().fromString("00:00:00", "HH:mm:ss"))
        self.start_time_edit.setDateTime(start_time)
        self.end_time_edit.setDateTime(end_time)

    def _emit_log(self, message):
        """发送日志到主界面"""
        self.log_message.emit(message)

    def on_query(self):
        start_time = self.start_time_edit.dateTime()
        end_time = self.end_time_edit.dateTime()

        if start_time >= end_time:
            QMessageBox.warning(self, "提示", "开始时间必须早于结束时间")
            return

        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.result_table.setRowCount(0)
        self.query_results = []
        self.export_btn.setEnabled(False)

        # 优先复用传入的device_query，否则重新创建
        if self.device_query and not self.device_query.init_error:
            token = self.device_query.token
            host = self.device_query.host
        else:
            from query_tool.utils.config import get_account_config
            from query_tool.utils.device_query import DeviceQuery
            env, username, password = get_account_config()
            if not username or not password:
                QMessageBox.warning(self, "错误", "未配置账号信息，请先在设置中配置")
                self.query_btn.setEnabled(True)
                self.query_btn.setText("开始查询")
                return
            dq = DeviceQuery(env, username, password)
            if dq.init_error:
                QMessageBox.warning(self, "错误", f"获取认证信息失败: {dq.init_error}")
                self.query_btn.setEnabled(True)
                self.query_btn.setText("开始查询")
                return
            token = dq.token
            host = dq.host

        self._emit_log(f"开始查询 {self.sn} 电池电量...")

        self.query_thread = DataCollectThread(
            self.sn, self.dev_id, 'battery',
            start_time.toString("yyyy-MM-dd HH:mm:ss"),
            end_time.toString("yyyy-MM-dd HH:mm:ss"),
            token, host
        )
        self.query_thread.finished.connect(self.on_query_finished)
        self.query_thread.log_message.connect(self._emit_log)
        self.query_thread.start()

    def on_query_finished(self, success, data, message):
        self.query_btn.setEnabled(True)
        self.query_btn.setText("开始查询")

        if success:
            self.query_results = data
            self.update_result_table()
            self.stats_label.setText(f"共查询到 {len(data)} 条记录")
            self.export_btn.setEnabled(len(data) > 0)
            self._emit_log(f"查询完成: {self.sn}，共 {len(data)} 条记录")
        else:
            QMessageBox.warning(self, "查询失败", message)
            self.stats_label.setText("共查询到 0 条记录")
            self._emit_log(f"查询失败: {self.sn}，{message}")

    def update_result_table(self):
        self.result_table.setRowCount(len(self.query_results))
        for row, item in enumerate(self.query_results):
            time_item = QTableWidgetItem(item.get('time', ''))
            time_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(row, 0, time_item)

            battery_item = QTableWidgetItem(str(item.get('battery', '')))
            battery_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(row, 1, battery_item)

    def on_export(self):
        if not self.query_results:
            self._emit_log("没有可导出的数据")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出数据",
            f"电池电量_{self.sn}_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.csv",
            "CSV文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['设备名称', 'SN', '采集时间', '电量(%)'])
                for item in self.query_results:
                    writer.writerow([self.device_name, self.sn, item.get('time', ''), item.get('battery', '')])
            import os
            self._emit_log(f"导出成功: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            self._emit_log(f"导出失败: {str(e)}")

    def closeEvent(self, event):
        if self.query_thread and self.query_thread.isRunning():
            self.query_thread.terminate()
            self.query_thread.wait()
        event.accept()
