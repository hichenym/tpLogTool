"""
批量设备固件升级对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QLineEdit, QComboBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QColor, QIcon
from .custom_widgets import set_dark_title_bar
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import requests


class NoWheelComboBox(QComboBox):
    """禁用鼠标滚轮切换的下拉框"""
    def wheelEvent(self, event):
        event.ignore()


class BatchStatusWorker(QObject):
    """批量状态查询工作器"""
    single_result = pyqtSignal(str, bool)  # (sn, is_online)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, token, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id, device_name, model), ...]
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
            from query_tool.utils import check_device_online
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
                    for sn, _, _, _ in self.devices
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
    
    def __init__(self, devices, token, host, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id), ...]
        self.token = token
        self.host = host
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
            success = wake_device_smart(dev_id, sn, self.token, self.host, max_times=3)
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
    
    def __init__(self, devices, token, host, max_workers=30):
        super().__init__()
        self.worker = BatchWakeWorker(devices, token, host, max_workers)
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
    
    def __init__(self, create_user='cur', device_identify='', audit_result='', page=1, per_page=100):
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
                per_page=self.per_page
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
    single_result = pyqtSignal(str, bool)  # (sn, success)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, device_identify, file_url, token, host, max_workers=30):
        super().__init__()
        self.devices = devices  # [(sn, dev_id), ...]
        self.device_identify = device_identify
        self.file_url = file_url
        self.token = token
        self.host = host
        self.max_workers = max_workers
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def upgrade_single_device(self, sn, dev_id):
        """升级单个设备"""
        if self._stop:
            return sn, False
        try:
            url = f"https://{self.host}/api/seetong-siot-device/console/device/operate/sendCommand"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": self.token,
            }
            
            params_dict = {
                "device_identify": self.device_identify,
                "file_url": self.file_url
            }
            params_json = json.dumps(params_dict)
            
            data = {
                "code": "upgrade",
                "params": params_json,
                "sn": sn,
                "sourceType": "1"
            }
            
            response = requests.post(url, json=data, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and result.get('success'):
                    return sn, True
                else:
                    return sn, False
            else:
                return sn, False
        except Exception as e:
            return sn, False
    
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
                    sn, success = future.result()
                    self.single_result.emit(sn, success)
                    completed += 1
                    if completed % 5 == 0 or completed == total:
                        self.progress.emit(f"升级进度: {completed}/{total}")
            
            self.all_done.emit()
        except Exception as e:
            self.all_done.emit()


class BatchUpgradeThread(QThread):
    """批量升级线程"""
    single_result = pyqtSignal(str, bool)
    all_done = pyqtSignal()
    progress = pyqtSignal(str)
    
    def __init__(self, devices, device_identify, file_url, token, host, max_workers=30):
        super().__init__()
        self.worker = BatchUpgradeWorker(devices, device_identify, file_url, token, host, max_workers)
        self.worker.single_result.connect(self.single_result)
        self.worker.all_done.connect(self.all_done)
        self.worker.progress.connect(self.progress)
    
    def run(self):
        self.worker.run()
    
    def stop(self):
        self.worker.stop()


class BatchUpgradeDialog(QDialog):
    """批量设备固件升级对话框"""
    
    def __init__(self, devices, device_query, thread_count, parent=None):
        """
        初始化批量升级对话框
        
        Args:
            devices: 设备列表 [(sn, dev_id, device_name, model), ...]
            device_query: DeviceQuery 对象
            thread_count: 线程数
            parent: 父窗口
        """
        super().__init__(parent)
        self.devices = devices
        self.device_query = device_query
        self.thread_count = thread_count
        self.parent_window = parent
        
        # 检查设备型号是否一致
        models = set(model for _, _, _, model in devices)
        self.has_single_model = len(models) == 1
        self.device_model = list(models)[0] if self.has_single_model else ""
        
        # 设备状态映射 {sn: is_online}
        self.device_status = {}
        
        # 固件相关
        self.firmware_list = []
        self.selected_firmware = None
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        
        # 线程
        self.status_thread = None
        self.wake_thread = None
        self.firmware_query_thread = None
        self.upgrade_thread = None
        
        self.init_ui()
        self.start_initial_query()
        
        # 如果设备型号一致，自动查询固件
        if self.has_single_model:
            self.query_firmware()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量设备固件升级")
        self.setFixedSize(950, 820)  # 增加高度到820，给固件列表底部更多空间
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)  # 减少主布局间距从15到12，让内容更紧凑
        
        # 设备列表分组
        device_group = QGroupBox("设备列表")
        device_layout = QVBoxLayout(device_group)
        device_layout.setContentsMargins(15, 20, 15, 15)
        device_layout.setSpacing(12)
        
        # 统计信息和按钮行
        info_button_layout = QHBoxLayout()
        info_button_layout.setSpacing(10)
        
        self.device_stats_label = QLabel("正在查询设备状态...")
        self.device_stats_label.setStyleSheet("color: #4A9EFF; font-size: 13px; font-weight: bold;")
        
        self.batch_wake_btn = QPushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(100, 28)
        self.batch_wake_btn.setEnabled(False)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        
        self.refresh_status_btn = QPushButton("刷新状态")
        self.refresh_status_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_status_btn.setIconSize(QSize(16, 16))
        self.refresh_status_btn.setFixedSize(100, 28)
        self.refresh_status_btn.setEnabled(False)
        self.refresh_status_btn.clicked.connect(self.on_refresh_status)
        
        info_button_layout.addWidget(self.device_stats_label)
        info_button_layout.addStretch()
        info_button_layout.addWidget(self.batch_wake_btn)
        info_button_layout.addWidget(self.refresh_status_btn)
        
        device_layout.addLayout(info_button_layout)
        
        # 设备列表表格
        self.device_table = QTableWidget()
        self.device_table.setColumnCount(4)
        self.device_table.setHorizontalHeaderLabels(["设备名称", "SN", "型号", "在线状态"])
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.setSelectionMode(QTableWidget.NoSelection)
        self.device_table.setFocusPolicy(Qt.NoFocus)
        
        # 计算表格高度：表头 + 5行数据（每行约30px）+ 边距
        row_height = 30
        header_height = 30
        max_visible_rows = 5
        table_height = header_height + (row_height * max_visible_rows) + 5
        self.device_table.setMaximumHeight(table_height)
        self.device_table.setMinimumHeight(table_height)
        
        from query_tool.utils import StyleManager
        StyleManager.apply_to_widget(self.device_table, "TABLE")
        
        header = self.device_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        
        # 计算列宽（总宽度约为 800 - 50 = 750）
        # 比例 3:4:2:2，总份数 = 11
        total_width = 750
        col2_width = int(total_width * 2 / 11)
        col3_width = int(total_width * 2 / 11)
        self.device_table.setColumnWidth(2, col2_width)
        self.device_table.setColumnWidth(3, col3_width)
        
        # 填充设备列表
        self.device_table.setRowCount(len(self.devices))
        for row, (sn, dev_id, device_name, model) in enumerate(self.devices):
            self.device_table.setItem(row, 0, QTableWidgetItem(device_name))
            self.device_table.setItem(row, 1, QTableWidgetItem(sn))
            self.device_table.setItem(row, 2, QTableWidgetItem(model))
            status_item = QTableWidgetItem("查询中...")
            status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
            self.device_table.setItem(row, 3, status_item)
        
        device_layout.addWidget(self.device_table)
        layout.addWidget(device_group)
        
        # 固件查询分组
        query_group = QGroupBox("固件查询")
        query_layout = QVBoxLayout(query_group)
        query_layout.setContentsMargins(15, 20, 15, 15)
        query_layout.setSpacing(12)
        
        # 查询条件框
        query_frame = QFrame()
        query_frame.setFrameShape(QFrame.StyledPanel)
        query_frame.setStyleSheet("QFrame { border: 1px solid #555555; background-color: transparent; }")
        query_frame_layout = QVBoxLayout(query_frame)
        query_frame_layout.setContentsMargins(8, 8, 8, 8)
        query_frame_layout.setSpacing(8)
        
        # 第一行：发布人员和审核状态
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        
        publisher_label = QLabel("发布人员:")
        publisher_label.setFixedWidth(70)
        publisher_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        publisher_label.setStyleSheet("border: none;")
        
        self.publisher_combo = NoWheelComboBox()
        self.publisher_combo.setFixedHeight(28)
        self.publisher_combo.addItem("当前登录用户", "cur")
        self.publisher_combo.addItem("全部", "all")
        
        audit_label = QLabel("审核状态:")
        audit_label.setFixedWidth(70)
        audit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        audit_label.setStyleSheet("border: none;")
        
        self.audit_combo = NoWheelComboBox()
        self.audit_combo.setFixedHeight(28)
        self.audit_combo.addItem("全部", "")
        self.audit_combo.addItem("无需审核", "1")
        self.audit_combo.addItem("待审核", "2")
        self.audit_combo.addItem("审核通过", "3")
        self.audit_combo.addItem("审核不通过", "4")
        
        row1_layout.addWidget(publisher_label)
        row1_layout.addWidget(self.publisher_combo, 1)
        row1_layout.addSpacing(10)
        row1_layout.addWidget(audit_label)
        row1_layout.addWidget(self.audit_combo, 1)
        
        query_frame_layout.addLayout(row1_layout)
        
        # 第二行：固件标识（与第一行布局保持一致）
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)
        
        identifier_label = QLabel("固件标识:")
        identifier_label.setFixedWidth(70)
        identifier_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        identifier_label.setStyleSheet("border: none;")
        
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("输入固件标识...")
        self.identifier_input.setFixedHeight(28)
        
        # 如果设备型号一致，自动填充并设置为只读
        if self.has_single_model:
            self.identifier_input.setText(self.device_model)
            self.identifier_input.setReadOnly(True)
            self.identifier_input.setStyleSheet("""
                QLineEdit {
                    background-color: #2b2b2b;
                    color: #909090;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 4px;
                }
            """)
        
        # 占位标签，与第一行的"审核状态:"标签宽度一致
        query_label_placeholder = QLabel("")
        query_label_placeholder.setFixedWidth(70)
        query_label_placeholder.setStyleSheet("border: none;")
        
        # 查询按钮容器，与第一行的审核状态下拉框宽度一致
        query_btn_container = QWidget()
        query_btn_layout = QHBoxLayout(query_btn_container)
        query_btn_layout.setContentsMargins(0, 0, 0, 0)
        query_btn_layout.setSpacing(0)
        
        self.query_firmware_btn = QPushButton("查询")
        self.query_firmware_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_firmware_btn.setFixedSize(80, 28)
        self.query_firmware_btn.clicked.connect(self.query_firmware)
        
        query_btn_layout.addWidget(self.query_firmware_btn)
        query_btn_layout.addStretch()
        
        row2_layout.addWidget(identifier_label)
        row2_layout.addWidget(self.identifier_input, 1)
        row2_layout.addSpacing(10)
        row2_layout.addWidget(query_label_placeholder)
        row2_layout.addWidget(query_btn_container, 1)
        
        query_frame_layout.addLayout(row2_layout)
        
        query_layout.addWidget(query_frame)
        layout.addWidget(query_group)
        
        # 固件列表分组
        list_group = QGroupBox("固件列表")
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(15, 20, 15, 20)  # 增加底部边距从15到20
        list_layout.setSpacing(15)  # 增加间距从12到15
        
        # 固件表格
        self.firmware_table = QTableWidget()
        self.firmware_table.setColumnCount(6)
        self.firmware_table.setHorizontalHeaderLabels(
            ["选择", "固件标识", "审核结果", "开始时间", "结束时间", "发布备注"]
        )
        self.firmware_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.firmware_table.setSelectionMode(QTableWidget.SingleSelection)
        self.firmware_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.firmware_table.setFocusPolicy(Qt.StrongFocus)
        self.firmware_table.setMinimumHeight(200)  # 与单设备升级对话框保持一致
        self.firmware_table.setMaximumHeight(200)
        self.firmware_table.setWordWrap(True)  # 启用自动换行
        StyleManager.apply_to_widget(self.firmware_table, "TABLE")
        
        # 连接行点击事件
        self.firmware_table.cellClicked.connect(self.on_table_cell_clicked)
        
        header = self.firmware_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        
        self.firmware_table.setColumnWidth(0, 50)   # 选择
        self.firmware_table.setColumnWidth(1, 280)  # 固件标识（加宽）
        self.firmware_table.setColumnWidth(2, 90)   # 审核结果
        self.firmware_table.setColumnWidth(3, 90)   # 开始时间（窄一些，换行显示）
        self.firmware_table.setColumnWidth(4, 90)   # 结束时间（窄一些，换行显示）
        # 发布备注使用 Stretch 自动填充剩余空间
        
        # 设置文本省略显示
        self.firmware_table.setTextElideMode(Qt.ElideRight)
        
        list_layout.addWidget(self.firmware_table)
        
        # 底部区域：翻页按钮（左）+ 统计信息（右）
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        
        # 翻页按钮（左侧）
        self.prev_page_btn = QPushButton()
        self.prev_page_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_page_btn.setIconSize(QSize(20, 20))
        self.prev_page_btn.setFixedSize(80, 28)
        self.prev_page_btn.setEnabled(False)
        self.prev_page_btn.clicked.connect(self.on_prev_page)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setFixedWidth(80)
        
        self.next_page_btn = QPushButton()
        self.next_page_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_page_btn.setIconSize(QSize(20, 20))
        self.next_page_btn.setFixedSize(80, 28)
        self.next_page_btn.setEnabled(False)
        self.next_page_btn.clicked.connect(self.on_next_page)
        
        bottom_layout.addWidget(self.prev_page_btn)
        bottom_layout.addWidget(self.page_label)
        bottom_layout.addWidget(self.next_page_btn)
        bottom_layout.addStretch()
        
        # 统计信息（右侧）
        self.firmware_stats_label = QLabel("未选择固件")
        self.firmware_stats_label.setStyleSheet("color: #4A9EFF; font-size: 13px;")
        bottom_layout.addWidget(self.firmware_stats_label)
        
        list_layout.addLayout(bottom_layout)
        
        layout.addWidget(list_group)
        
        # 底部按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        action_button_style = """
            QPushButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #6a6a6a;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #606060;
                border: 1px solid #3c3c3c;
            }
        """
        
        self.confirm_btn = QPushButton()
        self.confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.confirm_btn.setIconSize(QSize(20, 20))
        self.confirm_btn.setFixedSize(60, 32)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.setStyleSheet(action_button_style)
        self.confirm_btn.clicked.connect(self.on_confirm)
        
        self.cancel_btn = QPushButton()
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(20, 20))
        self.cancel_btn.setFixedSize(60, 32)
        self.cancel_btn.setStyleSheet(action_button_style)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def start_initial_query(self):
        """开始初始查询设备状态"""
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        self.status_thread.single_result.connect(self.on_status_result)
        self.status_thread.all_done.connect(self.on_status_query_complete)
        self.status_thread.start()
    
    def on_status_result(self, sn, is_online):
        """单个设备状态查询结果"""
        self.device_status[sn] = is_online
        
        # 更新表格
        for row in range(self.device_table.rowCount()):
            sn_item = self.device_table.item(row, 1)
            if sn_item and sn_item.text() == sn:
                status_item = self.device_table.item(row, 3)
                if is_online:
                    status_item.setText("在线")
                    status_item.setData(Qt.ForegroundRole, QColor(Qt.green))
                else:
                    status_item.setText("离线")
                    status_item.setData(Qt.ForegroundRole, QColor(Qt.red))
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
        
        self.device_stats_label.setText(
            f"{online_count} 台在线  |  {offline_count} 台离线"
        )
    
    def on_batch_wake(self):
        """批量唤醒"""
        # 获取所有离线设备
        offline_devices = []
        for sn, dev_id, device_name, model in self.devices:
            if not self.device_status.get(sn, False):
                offline_devices.append((sn, dev_id))
        
        if not offline_devices:
            if self.parent_window:
                self.parent_window.show_info("没有离线设备需要唤醒")
            return
        
        # 禁用按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_status_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 更新表格显示"唤醒中..."
        for sn, _ in offline_devices:
            for row in range(self.device_table.rowCount()):
                sn_item = self.device_table.item(row, 1)
                if sn_item and sn_item.text() == sn:
                    status_item = self.device_table.item(row, 3)
                    status_item.setText("唤醒中...")
                    status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
                    break
        
        # 启动唤醒线程
        self.wake_thread = BatchWakeThread(
            offline_devices,
            self.device_query.token,
            self.device_query.host,
            self.thread_count
        )
        self.wake_thread.all_done.connect(self.on_wake_complete)
        self.wake_thread.start()
    
    def on_wake_complete(self):
        """唤醒完成，自动刷新状态"""
        self.on_refresh_status()
    
    def on_refresh_status(self):
        """刷新设备状态"""
        # 禁用按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_status_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 更新表格显示"查询中..."
        for row in range(self.device_table.rowCount()):
            status_item = self.device_table.item(row, 3)
            status_item.setText("查询中...")
            status_item.setData(Qt.ForegroundRole, QColor("#FFA500"))
        
        self.device_stats_label.setText("正在查询设备状态...")
        
        # 启动查询线程
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        self.status_thread.single_result.connect(self.on_status_result)
        self.status_thread.all_done.connect(self.on_status_query_complete)
        self.status_thread.start()
    
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
        
        self.firmware_query_thread = FirmwareQueryThread(
            create_user=create_user,
            device_identify=device_identify,
            audit_result=audit_result,
            page=page,
            per_page=100
        )
        self.firmware_query_thread.finished_signal.connect(self.on_firmware_query_finished)
        self.firmware_query_thread.error_signal.connect(self.on_firmware_query_error)
        self.firmware_query_thread.start()
    
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
        
        # 计算起始序号：(当前页-1) * 每页条数 + 1
        start_index = (self.current_page - 1) * 100 + 1
        
        # 审核结果颜色映射
        audit_result_color_map = {
            '无需审核': '#909090',      # 灰色
            '待审核': '#FFA500',        # 橙色
            '审核通过': '#00FF00',      # 绿色
            '审核不通过': '#FF0000',    # 红色
        }
        
        # 创建单选按钮组
        self.radio_group = QButtonGroup(self)
        self.radio_group.buttonClicked.connect(self.on_firmware_selected)
        
        for row, firmware in enumerate(self.firmware_list):
            # 设置行号（垂直表头）
            actual_row_number = start_index + row
            self.firmware_table.setVerticalHeaderItem(row, QTableWidgetItem(str(actual_row_number)))
            
            # 选择列（单选框）
            radio = QRadioButton()
            radio_widget = QWidget()
            radio_layout = QHBoxLayout(radio_widget)
            radio_layout.addWidget(radio)
            radio_layout.setAlignment(Qt.AlignCenter)
            radio_layout.setContentsMargins(0, 0, 0, 0)
            self.firmware_table.setCellWidget(row, 0, radio_widget)
            self.radio_group.addButton(radio, row)
            
            # 固件标识（使用 identifier 字段）
            item = QTableWidgetItem(firmware.get('identifier', ''))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.firmware_table.setItem(row, 1, item)
            
            # 审核结果（添加颜色）
            audit_result = firmware.get('audit_result', '')
            item = QTableWidgetItem(audit_result)
            item.setTextAlignment(Qt.AlignCenter)
            # 根据审核结果设置颜色
            audit_color = audit_result_color_map.get(audit_result, '#909090')  # 默认灰色
            item.setData(Qt.ForegroundRole, QColor(audit_color))
            self.firmware_table.setItem(row, 2, item)
            
            # 开始时间
            item = QTableWidgetItem(firmware.get('start_time', ''))
            item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 3, item)
            
            # 结束时间
            item = QTableWidgetItem(firmware.get('end_time', ''))
            item.setTextAlignment(Qt.AlignCenter)
            self.firmware_table.setItem(row, 4, item)
            
            # 发布备注（使用 remark 字段）
            item = QTableWidgetItem(firmware.get('remark', ''))
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.firmware_table.setItem(row, 5, item)
        
        # 调整行高以适应内容（支持换行）
        self.firmware_table.resizeRowsToContents()
    
    def on_firmware_selected(self, button):
        """固件选择事件"""
        row = self.radio_group.id(button)
        if 0 <= row < len(self.firmware_list):
            self.selected_firmware = self.firmware_list[row]
            device_identify = self.selected_firmware.get('identifier', '')
            self.firmware_stats_label.setText(f"已选择: {device_identify}")
            self.update_confirm_button()
            # 高亮选中行
            self.firmware_table.selectRow(row)
    
    def on_table_cell_clicked(self, row, column):
        """表格单元格点击事件"""
        if 0 <= row < len(self.firmware_list):
            # 更新单选框
            radio_widget = self.firmware_table.cellWidget(row, 0)
            if radio_widget:
                radio = radio_widget.findChild(QRadioButton)
                if radio:
                    radio.setChecked(True)
                    # 触发选择事件
                    self.selected_firmware = self.firmware_list[row]
                    device_identify = self.selected_firmware.get('identifier', '')
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
        # 只有在设备型号一致且选择了固件时才能启用确认按钮
        self.confirm_btn.setEnabled(self.has_single_model and self.selected_firmware is not None)
    
    def on_confirm(self):
        """确认升级"""
        # 检查设备型号是否一致
        if not self.has_single_model:
            if self.parent_window:
                self.parent_window.show_error("所选设备型号不一致，无法进行批量升级")
            return
        
        if not self.selected_firmware:
            if self.parent_window:
                self.parent_window.show_warning("请先选择固件")
            return
        
        # 禁用所有按钮
        self.batch_wake_btn.setEnabled(False)
        self.refresh_status_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 重新查询所有设备状态（后台查询，不更新界面）
        self.status_thread = BatchStatusThread(
            self.devices,
            self.device_query.token,
            self.thread_count
        )
        self.status_thread.single_result.connect(self.on_status_result_silent)
        self.status_thread.all_done.connect(self.on_final_query_complete)
        self.status_thread.start()
    
    def on_status_result_silent(self, sn, is_online):
        """静默更新设备状态（不更新表格显示）"""
        self.device_status[sn] = is_online
    
    def on_final_query_complete(self):
        """最终查询完成，开始升级"""
        # 获取所有在线设备
        online_devices = []
        for sn, dev_id, device_name, model in self.devices:
            if self.device_status.get(sn, False):
                online_devices.append((sn, dev_id))
        
        online_count = len(online_devices)
        offline_count = len(self.devices) - online_count
        
        if online_count == 0:
            if self.parent_window:
                self.parent_window.show_error("设备离线，操作失败")
            self.restore_buttons()
            return
        
        # 获取固件信息
        device_identify = self.selected_firmware.get('identifier', '')
        file_url = self.selected_firmware.get('download_url', '')
        
        if not file_url:
            if self.parent_window:
                self.parent_window.show_error("固件下载链接为空，无法升级")
            self.restore_buttons()
            return
        
        # 启动升级线程
        self.upgrade_thread = BatchUpgradeThread(
            online_devices,
            device_identify,
            file_url,
            self.device_query.token,
            self.device_query.host,
            self.thread_count
        )
        self.upgrade_thread.all_done.connect(
            lambda: self.on_upgrade_complete(online_count, offline_count)
        )
        self.upgrade_thread.start()
    
    def on_upgrade_complete(self, online_count, offline_count):
        """升级完成"""
        if self.parent_window:
            self.parent_window.show_success(
                f"升级命令已发送：成功 {online_count} 台，离线 {offline_count} 台"
            )
        self.accept()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.batch_wake_btn.setEnabled(True)
        self.refresh_status_btn.setEnabled(True)
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
        
        if self.upgrade_thread and self.upgrade_thread.isRunning():
            self.upgrade_thread.stop()
            self.upgrade_thread.quit()
            self.upgrade_thread.wait(1000)
        
        event.accept()
