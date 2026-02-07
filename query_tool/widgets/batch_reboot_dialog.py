"""
批量重启对话框
支持批量查询在线状态、批量唤醒、批量重启
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QColor, QIcon
from concurrent.futures import ThreadPoolExecutor, as_completed

from query_tool.utils import StyleManager, check_device_online, wake_device_smart
from query_tool.widgets.custom_widgets import set_dark_title_bar


class BatchStatusWorker(QObject):
    """批量状态查询工作器"""
    single_result = pyqtSignal(str, bool)  # (sn, is_online)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, token, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id, device_name), ...]
        self.token = token
        self.max_workers = max_workers
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def check_single_device(self, sn):
        """查询单个设备在线状态"""
        if self._stop:
            return sn, False
        try:
            is_online = check_device_online(sn, self.token)
            return sn, is_online
        except Exception as e:
            return sn, False
    
    def run(self):
        try:
            total = len(self.devices)
            completed = 0
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.check_single_device, sn): sn
                    for sn, _, _ in self.devices
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
        except Exception as e:
            self.all_done.emit()


class BatchStatusThread(QThread):
    """批量状态查询线程"""
    single_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, token, max_workers=30):
        super().__init__()
        self.worker = BatchStatusWorker(devices, token, max_workers)
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
    
    def __init__(self, devices, token, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id), ...]
        self.token = token
        self.max_workers = max_workers
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def wake_single_device(self, sn, dev_id):
        """唤醒单个设备"""
        if self._stop:
            return sn, False
        try:
            success = wake_device_smart(dev_id, sn, self.token, max_times=3)
            return sn, success
        except Exception as e:
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
        except Exception as e:
            self.all_done.emit()


class BatchWakeThread(QThread):
    """批量唤醒线程"""
    single_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, token, max_workers=30):
        super().__init__()
        self.worker = BatchWakeWorker(devices, token, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)
    
    def run(self):
        self.worker.run()
    
    def stop(self):
        self.worker.stop()


class BatchRebootWorker(QObject):
    """批量重启工作器"""
    single_result = pyqtSignal(str, bool)  # (sn, success)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, reboot_time, device_query, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id), ...]
        self.reboot_time = reboot_time
        self.device_query = device_query
        self.max_workers = max_workers
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def reboot_single_device(self, sn, dev_id):
        """重启单个设备"""
        if self._stop:
            return sn, False
        try:
            success = self.device_query.send_reboot_command(dev_id, self.reboot_time)
            return sn, success
        except Exception as e:
            return sn, False
    
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
                    sn, success = future.result()
                    self.single_result.emit(sn, success)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"重启进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
            self.all_done.emit()


class BatchRebootThread(QThread):
    """批量重启线程"""
    single_result = pyqtSignal(str, bool)
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


class BatchRebootDialog(QDialog):
    """批量重启对话框"""
    
    def __init__(self, devices, device_query, thread_count, parent=None):
        """
        初始化批量重启对话框
        
        Args:
            devices: 设备列表 [(sn, dev_id, device_name), ...]
            device_query: DeviceQuery 对象
            thread_count: 线程数
            parent: 父窗口
        """
        super().__init__(parent)
        self.devices = devices
        self.device_query = device_query
        self.thread_count = thread_count
        self.parent_window = parent
        
        # 设备状态映射 {sn: is_online}
        self.device_status = {}
        
        # 线程
        self.status_thread = None
        self.wake_thread = None
        self.reboot_thread = None
        
        self.init_ui()
        self.start_initial_query()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量重启设备")
        self.setFixedSize(600, 430)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 设备列表分组
        operation_group = QGroupBox("设备列表")
        operation_layout = QVBoxLayout(operation_group)
        operation_layout.setContentsMargins(15, 20, 15, 15)
        operation_layout.setSpacing(12)
        
        # 统计信息和按钮行
        info_button_layout = QHBoxLayout()
        info_button_layout.setSpacing(10)
        
        self.stats_label = QLabel("正在查询设备状态...")
        self.stats_label.setStyleSheet("color: #4A9EFF; font-size: 13px; font-weight: bold;")
        
        self.batch_wake_btn = QPushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(100, 28)
        self.batch_wake_btn.setEnabled(False)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(100, 28)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.on_refresh_status)
        
        info_button_layout.addWidget(self.stats_label)
        info_button_layout.addStretch()
        info_button_layout.addWidget(self.batch_wake_btn)
        info_button_layout.addWidget(self.refresh_btn)
        
        operation_layout.addLayout(info_button_layout)
        
        # 设备列表表格
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(3)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "在线状态"])
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(QTableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        self.device_table.setFixedHeight(200)
        StyleManager.apply_to_widget(self.device_table, "TABLE")
        
        # 设置列宽 - 按比例 3:4:2
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        
        # 计算列宽（总宽度约为 600 - 50(边距) - 20(滚动条) = 530）
        # 比例 3:4:2，总份数 = 9
        total_width = 530
        col2_width = int(total_width * 2 / 9)  # 2/9
        self.device_table.setColumnWidth(2, col2_width)
        
        # 填充设备列表
        self.device_table.setRowCount(len(self.devices))
        for row, (sn, dev_id, device_name) in enumerate(self.devices):
            self.device_table.setItem(row, 0, QTableWidgetItem(device_name))
            self.device_table.setItem(row, 1, QTableWidgetItem(sn))
            status_item = QTableWidgetItem("查询中...")
            status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
            self.device_table.setItem(row, 2, status_item)
        
        operation_layout.addWidget(self.device_table)
        layout.addWidget(operation_group)
        
        # 重启时间选择
        time_group = QGroupBox("重启时间")
        time_layout = QHBoxLayout(time_group)
        time_layout.setContentsMargins(15, 20, 15, 15)
        
        self.time_group = QButtonGroup(self)
        self.now_radio = QRadioButton("立即重启")
        self.later_radio = QRadioButton("5分钟后重启")
        self.now_radio.setChecked(True)
        
        self.time_group.addButton(self.now_radio, 0)
        self.time_group.addButton(self.later_radio, 1)
        
        time_layout.addWidget(self.now_radio)
        time_layout.addWidget(self.later_radio)
        time_layout.addStretch()
        
        layout.addWidget(time_group)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.confirm_btn = QPushButton()
        self.confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.confirm_btn.setIconSize(QSize(20, 20))
        self.confirm_btn.setFixedSize(60, 32)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.on_confirm)
        
        self.cancel_btn = QPushButton()
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(20, 20))
        self.cancel_btn.setFixedSize(60, 32)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def start_initial_query(self):
        """开始初始查询"""
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        self.status_thread.single_result.connect(self.on_status_result)
        self.status_thread.all_done.connect(self.on_query_complete)
        self.status_thread.start()
    
    def on_status_result(self, sn, is_online):
        """单个设备状态查询结果"""
        self.device_status[sn] = is_online
        
        # 更新表格
        for row in range(self.device_table.rowCount()):
            sn_item = self.device_table.item(row, 1)
            if sn_item and sn_item.text() == sn:
                status_item = self.device_table.item(row, 2)
                if is_online:
                    status_item.setText("在线")
                    status_item.setData(Qt.ForegroundRole, QColor(Qt.green))
                else:
                    status_item.setText("离线")
                    status_item.setData(Qt.ForegroundRole, QColor(Qt.red))
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
        
        self.stats_label.setText(
            f"{online_count} 台将重启  |  {offline_count} 台跳过"
        )
    
    def on_batch_wake(self):
        """批量唤醒"""
        # 获取所有离线设备
        offline_devices = []
        for sn, dev_id, device_name in self.devices:
            if not self.device_status.get(sn, False):
                offline_devices.append((sn, dev_id))
        
        if not offline_devices:
            if self.parent_window:
                self.parent_window.show_info("没有离线设备需要唤醒")
            return
        
        # 禁用按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 更新表格显示"唤醒中..."
        for sn, _ in offline_devices:
            for row in range(self.device_table.rowCount()):
                sn_item = self.device_table.item(row, 1)
                if sn_item and sn_item.text() == sn:
                    status_item = self.device_table.item(row, 2)
                    status_item.setText("唤醒中...")
                    status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
                    break
        
        # 启动唤醒线程
        self.wake_thread = BatchWakeThread(
            offline_devices,
            self.device_query.token,
            self.thread_count
        )
        self.wake_thread.all_done.connect(self.on_wake_complete)
        self.wake_thread.start()  # 启动线程
        self.wake_thread.start()
    
    def on_wake_complete(self):
        """唤醒完成，自动刷新状态"""
        self.on_refresh_status()
    
    def on_refresh_status(self):
        """刷新状态"""
        # 禁用按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 更新表格显示"查询中..."
        for row in range(self.device_table.rowCount()):
            status_item = self.device_table.item(row, 2)
            status_item.setText("查询中...")
            status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
        
        self.stats_label.setText("正在查询设备状态...")
        
        # 启动查询线程
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        self.status_thread.single_result.connect(self.on_status_result)
        self.status_thread.all_done.connect(self.on_query_complete)
        self.status_thread.start()
    
    def on_confirm(self):
        """确认重启"""
        # 禁用所有按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 重新查询所有设备状态（后台查询，不更新界面）
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        # 连接到后台更新方法（只更新状态字典，不更新表格）
        self.status_thread.single_result.connect(self.on_status_result_silent)
        self.status_thread.all_done.connect(self.on_final_query_complete)
        self.status_thread.start()
    
    def on_status_result_silent(self, sn, is_online):
        """静默更新设备状态（不更新表格显示）"""
        self.device_status[sn] = is_online
    
    def on_final_query_complete(self):
        """最终查询完成，开始重启"""
        # 获取所有在线设备
        online_devices = []
        for sn, dev_id, device_name in self.devices:
            if self.device_status.get(sn, False):
                online_devices.append((sn, dev_id))
        
        online_count = len(online_devices)
        offline_count = len(self.devices) - online_count
        
        if online_count == 0:
            if self.parent_window:
                self.parent_window.show_error("设备离线，操作失败")
            self.restore_buttons()
            return
        
        # 获取重启时间
        reboot_time = "now" if self.now_radio.isChecked() else "after_five_minute"
        
        # 启动重启线程
        self.reboot_thread = BatchRebootThread(
            online_devices,
            reboot_time,
            self.device_query,
            self.thread_count
        )
        self.reboot_thread.all_done.connect(
            lambda: self.on_reboot_complete(online_count, offline_count)
        )
        self.reboot_thread.start()
    
    def on_reboot_complete(self, online_count, offline_count):
        """重启完成"""
        if self.parent_window:
            self.parent_window.show_success(
                f"重启命令已发送：成功 {online_count} 台，离线 {offline_count} 台"
            )
        self.accept()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.batch_wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
    
    def closeEvent(self, event):
        """关闭事件"""
        # 停止所有线程
        if self.status_thread and self.status_thread.isRunning():
            self.status_thread.stop()
            self.status_thread.quit()
            self.status_thread.wait(1000)
        
        if self.wake_thread and self.wake_thread.isRunning():
            self.wake_thread.stop()
            self.wake_thread.quit()
            self.wake_thread.wait(1000)
        
        if self.reboot_thread and self.reboot_thread.isRunning():
            self.reboot_thread.stop()
            self.reboot_thread.quit()
            self.reboot_thread.wait(1000)
        
        event.accept()
