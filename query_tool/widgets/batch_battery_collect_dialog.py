"""
批量电池电量数据采集对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QGroupBox, QHeaderView, QMessageBox, QFileDialog,
                             QDateTimeEdit, QProgressBar, QWidget)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtGui import QIcon
from query_tool.widgets.custom_widgets import set_dark_title_bar
from query_tool.utils.theme_manager import t
from query_tool.utils import StyleManager
from query_tool.utils.data_collect_api import BatchDataCollectThread
from query_tool.utils.logger import logger
import csv


class BatchBatteryCollectDialog(QDialog):
    """批量电池电量数据采集对话框"""

    # 日志信号，发送到主界面左下角
    log_message = pyqtSignal(str)

    def __init__(self, devices, thread_count, device_query=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.thread_count = thread_count
        self.device_query = device_query  # 复用已有的DeviceQuery对象
        self.query_thread = None
        self.all_results = []
        self.device_status = {}
        self.resize_timer = None
        self.init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        self.adjust_table_columns()

    def init_ui(self):
        self.setWindowTitle("电池电量批量采集")
        self.setFixedSize(900, 700)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        device_count_label = QLabel(f"已选择 {len(self.devices)} 台设备，线程数: {self.thread_count}")
        device_count_label.setStyleSheet(f"color: {t('status_info')}; font-size: 14px;")
        layout.addWidget(device_count_label)

        # 查询配置分组
        config_group = QGroupBox("查询配置")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(15, 20, 15, 15)
        config_layout.setSpacing(12)

        datetime_style = ""  # 全局 QSS 已覆盖 QDateTimeEdit

        time_row1 = QWidget()
        time_row1_layout = QHBoxLayout(time_row1)
        time_row1_layout.setContentsMargins(0, 0, 0, 0)
        time_row1_layout.setSpacing(10)

        time_range_label = QLabel("时间范围:")
        time_range_label.setFixedWidth(70)
        time_range_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")

        self.start_time_edit = QDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        start_dt = QDateTime.currentDateTime().addDays(-6)
        start_dt.setTime(start_dt.time().fromString("00:00:00", "HH:mm:ss"))
        self.start_time_edit.setDateTime(start_dt)
        self.start_time_edit.setStyleSheet(datetime_style)

        separator_label = QLabel("至")
        separator_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px;")
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

        btn_style = StyleManager.get_ACTION_BUTTON()

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

        # 查询进度分组
        progress_group = QGroupBox("查询进度")
        progress_layout = QVBoxLayout(progress_group)
        progress_layout.setContentsMargins(15, 20, 15, 15)
        progress_layout.setSpacing(12)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "记录数"])
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(QTableWidget.SingleSelection)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setMinimumHeight(200)

        StyleManager.apply_to_widget(self.device_table, "TABLE")

        header = self.device_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.device_table.setColumnWidth(0, 300)
        self.device_table.setColumnWidth(1, 200)
        self.device_table.setColumnWidth(2, 150)
        self.device_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.device_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        header.sectionResized.connect(self.on_column_resized)

        self.init_device_table()
        progress_layout.addWidget(self.device_table)

        # 提示文本
        tip_label = QLabel("提示: 双击记录数查看单台详情数据")
        tip_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        progress_layout.addWidget(tip_label)

        # 双击记录数列弹出详情
        self.device_table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(len(self.devices))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m (%p%)")
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t('border')}; border-radius: 3px;
                background-color: {t('bg_mid')}; text-align: center;
                color: {t('text_primary')}; height: 20px;
            }}
            QProgressBar::chunk {{ background-color: {t('status_info')}; }}
        """)
        progress_layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("成功: 0 台  失败: 0 台  总记录: 0 条")
        self.stats_label.setStyleSheet(f"color: {t('status_info')}; font-size: 12px;")
        progress_layout.addWidget(self.stats_label)

        layout.addWidget(progress_group)

        # 底部按钮
        button_layout = QHBoxLayout()

        self.export_btn = QPushButton("导出结果")
        self.export_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_btn.setFixedSize(100, 32)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet(btn_style)
        self.export_btn.clicked.connect(self.on_export)
        button_layout.addWidget(self.export_btn)
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
        if not hasattr(self, 'device_table'):
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
            name_item = QTableWidgetItem(device.get('device_name', ''))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # 存储设备信息供双击时使用
            name_item.setData(Qt.UserRole, device)
            self.device_table.setItem(row, 0, name_item)

            sn = device.get('sn', '')
            sn_item = QTableWidgetItem(sn)
            sn_item.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(row, 1, sn_item)

            count_item = QTableWidgetItem("-")
            count_item.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(row, 2, count_item)

            self.device_status[sn] = {'row': row, 'status': 'waiting', 'count': 0}

    def on_cell_double_clicked(self, row, col):
        """双击记录数列弹出该设备的电池电量详情"""
        # 只响应记录数列（col=2），且必须有查询结果
        if col != 2:
            return

        sn_item = self.device_table.item(row, 1)
        if not sn_item:
            return
        sn = sn_item.text()

        # 查找该设备的查询结果
        device_data = None
        device_info = None
        for result in self.all_results:
            if result.get('sn') == sn and result.get('success'):
                device_data = result['data']
                break

        if not device_data:
            self._emit_log(f"暂无 {sn} 的查询数据，请先执行查询")
            return

        # 从 name_item 的 UserRole 取设备信息
        name_item = self.device_table.item(row, 0)
        device_info = name_item.data(Qt.UserRole) if name_item else {}
        device_name = device_info.get('device_name', '') if device_info else ''
        model = device_info.get('model', '') if device_info else ''
        dev_id = device_info.get('dev_id', '') if device_info else ''

        from query_tool.widgets.battery_collect_dialog import BatteryCollectDialog
        dialog = BatteryCollectDialog(
            sn, dev_id, device_name, model,
            device_query=self.device_query,
            parent=self,
            prefill_data=device_data
        )
        dialog.log_message.connect(self._emit_log)
        dialog.exec_()

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
        self.all_results = []
        self.progress_bar.setValue(0)

        # 重置表格状态
        for sn, info in self.device_status.items():
            row = info['row']
            item = self.device_table.item(row, 2)
            if item:
                item.setText("-")

        # 优先复用传入的device_query
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

        self._emit_log(f"开始批量查询 {len(self.devices)} 台设备电池电量，线程数: {self.thread_count}")

        self.query_thread = BatchDataCollectThread(
            self.devices, 'battery',
            start_time.toString("yyyy-MM-dd HH:mm:ss"),
            end_time.toString("yyyy-MM-dd HH:mm:ss"),
            token, host,
            self.thread_count
        )
        self.query_thread.progress.connect(self.on_device_progress)
        self.query_thread.finished.connect(self.on_query_complete)
        self.query_thread.log_message.connect(self._emit_log)
        self.query_thread.start()

    def on_device_progress(self, sn, status, record_count, message):
        if sn not in self.device_status:
            return
        row = self.device_status[sn]['row']
        if status == 'success':
            self.device_table.item(row, 2).setText(f"{record_count}条")
            self.device_status[sn]['status'] = 'success'
            self.device_status[sn]['count'] = record_count
            self.progress_bar.setValue(self.progress_bar.value() + 1)
        elif status == 'failed':
            self.device_table.item(row, 2).setText("失败")
            self.device_status[sn]['status'] = 'failed'
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
            self, "导出数据",
            f"批量电池电量_{QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss')}.csv",
            "CSV文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['设备名称', 'SN', '型号', '采集时间', '电量(%)'])
                for result in self.all_results:
                    if result['success']:
                        for item in result['data']:
                            writer.writerow([
                                result.get('device_name', ''),
                                result.get('sn', ''),
                                result.get('model', ''),
                                item.get('time', ''),
                                item.get('battery', '')
                            ])
            import os
            self._emit_log(f"导出成功: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"导出数据失败: {e}")
            self._emit_log(f"导出失败: {str(e)}")

    def closeEvent(self, event):
        if self.query_thread and self.query_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认", "查询正在进行中，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.query_thread.stop()
                self.query_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


