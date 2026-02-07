"""
设备固件升级对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QLineEdit, QComboBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon
from .custom_widgets import set_dark_title_bar
import json
import requests


class NoWheelComboBox(QComboBox):
    """禁用鼠标滚轮切换的下拉框"""
    def wheelEvent(self, event):
        event.ignore()


class StatusQueryThread(QThread):
    """状态查询线程"""
    finished_signal = pyqtSignal(bool, str)  # is_online, message
    
    def __init__(self, sn, token):
        super().__init__()
        self.sn = sn
        self.token = token
    
    def run(self):
        try:
            from query_tool.utils import check_device_online
            is_online = check_device_online(self.sn, self.token)
            if is_online:
                self.finished_signal.emit(True, "在线")
            else:
                self.finished_signal.emit(False, "离线")
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
                self.device_query.token, 
                self.device_query.host,
                max_times=3
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


class UpgradeThread(QThread):
    """升级命令发送线程"""
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, sn, device_identify, file_url, token, host):
        super().__init__()
        self.sn = sn
        self.device_identify = device_identify
        self.file_url = file_url
        self.token = token
        self.host = host
    
    def run(self):
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
                "sn": self.sn,
                "sourceType": "1"
            }
            
            response = requests.post(url, json=data, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and result.get('success'):
                    self.finished_signal.emit(True, "升级命令已发送")
                elif result.get('code') == 20001:
                    self.finished_signal.emit(False, "设备不在线，操作失败")
                else:
                    msg = result.get('msg', '操作失败')
                    self.finished_signal.emit(False, msg)
            else:
                self.finished_signal.emit(False, f"HTTP {response.status_code}")
        except Exception as e:
            self.finished_signal.emit(False, f"升级出错: {str(e)}")


class UpgradeDialog(QDialog):
    """设备固件升级对话框"""
    
    def __init__(self, sn, dev_id, device_name, model, device_query, parent=None):
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_name = device_name
        self.model = model
        self.device_query = device_query
        self.parent_window = parent
        
        # 状态
        self.is_online = False
        self.selected_firmware = None  # {id, identifier, download_url, ...}
        
        # 线程
        self.status_query_thread = None
        self.wake_thread = None
        self.firmware_query_thread = None
        self.upgrade_thread = None
        
        # 固件列表和分页
        self.firmware_list = []
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        
        self.init_ui()
        
        # 初始化：查询在线状态 + 查询固件列表
        self.query_status()
        self.query_firmware()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设备固件升级")
        self.setFixedSize(900, 580)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 设备信息
        info_label = QLabel(f"设备: {self.device_name}    SN: {self.sn}    型号: {self.model}")
        info_label.setStyleSheet("color: #4a9eff; font-size: 13px;")
        layout.addWidget(info_label)
        
        # 在线状态区
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)
        
        status_label_text = QLabel("在线状态:")
        status_label_text.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        status_label_text.setFixedWidth(70)
        status_label_text.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.status_label = QLabel("● 查询中...")
        self.status_label.setStyleSheet("color: #909090; font-size: 12px;")
        self.status_label.setFixedWidth(80)
        
        self.wake_btn = QPushButton()
        self.wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.wake_btn.setIconSize(QSize(16, 16))
        self.wake_btn.setFixedSize(28, 28)
        self.wake_btn.setEnabled(False)
        self.wake_btn.setToolTip("唤醒设备")
        self.wake_btn.clicked.connect(self.on_wake)
        
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("刷新状态")
        self.refresh_btn.clicked.connect(self.on_refresh)
        
        button_style = """
            QPushButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 0px;
                font-size: 16px;
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
        self.wake_btn.setStyleSheet(button_style)
        self.refresh_btn.setStyleSheet(button_style)
        
        status_layout.addWidget(status_label_text)
        status_layout.addWidget(self.status_label)
        status_layout.addSpacing(5)
        status_layout.addWidget(self.wake_btn)
        status_layout.addSpacing(5)
        status_layout.addWidget(self.refresh_btn)
        status_layout.addStretch()
        
        layout.addWidget(status_widget)
        
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
        self.identifier_input.setText(self.model)  # 默认填充型号
        self.identifier_input.setReadOnly(True)  # 设置为只读，不允许修改
        self.identifier_input.setFixedHeight(28)
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
        list_layout.setContentsMargins(15, 20, 15, 15)
        list_layout.setSpacing(12)
        
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
        self.firmware_table.setMinimumHeight(200)
        self.firmware_table.setMaximumHeight(200)
        self.firmware_table.setWordWrap(True)  # 启用自动换行
        
        from query_tool.utils import StyleManager
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
        self.firmware_table.setColumnWidth(1, 250)  # 固件标识（加宽）
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
        self.stats_label = QLabel("未选择固件")
        self.stats_label.setStyleSheet("color: #4A9EFF; font-size: 13px;")
        bottom_layout.addWidget(self.stats_label)
        
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
    
    def query_status(self):
        """查询设备在线状态"""
        self.status_label.setText("● 查询中...")
        self.status_label.setStyleSheet("color: #909090; font-size: 12px;")
        
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        
        if self.device_query and not self.device_query.init_error:
            self.status_query_thread = StatusQueryThread(self.sn, self.device_query.token)
            self.status_query_thread.finished_signal.connect(self.on_status_query_finished)
            self.status_query_thread.start()
        else:
            self.status_label.setText("● 查询失败")
            self.status_label.setStyleSheet("color: #909090; font-size: 12px;")
    
    def on_status_query_finished(self, is_online, message):
        """状态查询完成"""
        self.is_online = is_online
        
        if is_online:
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
        else:
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
        
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.update_confirm_button()
    
    def on_refresh(self):
        """刷新状态"""
        self.query_status()
    
    def on_wake(self):
        """唤醒设备"""
        self.status_label.setText("● 唤醒中...")
        self.status_label.setStyleSheet("color: #FFA500; font-size: 12px;")
        
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        
        self.wake_thread = WakeDeviceThread(self.dev_id, self.sn, self.device_query)
        self.wake_thread.finished_signal.connect(self.on_wake_finished)
        self.wake_thread.start()
    
    def on_wake_finished(self, success, message):
        """唤醒完成"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        
        if success:
            self.is_online = True
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
        else:
            if self.is_online:
                self.status_label.setText("● 在线")
                self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
            else:
                self.status_label.setText("● 离线")
                self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
        
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
            self.stats_label.setText(f"已选择: {device_identify}")
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
        # 只有选择了固件才能启用确认按钮
        self.confirm_btn.setEnabled(self.selected_firmware is not None)
    
    def on_confirm(self):
        """确认升级"""
        if not self.selected_firmware:
            if self.parent_window:
                self.parent_window.show_warning("请先选择固件")
            return
        
        # 禁用所有按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 重新查询状态
        if self.device_query and not self.device_query.init_error:
            self.status_query_thread = StatusQueryThread(self.sn, self.device_query.token)
            self.status_query_thread.finished_signal.connect(self.on_confirm_status_checked)
            self.status_query_thread.start()
        else:
            if self.parent_window:
                self.parent_window.show_error("查询状态失败，操作取消")
            self.restore_buttons()
    
    def on_confirm_status_checked(self, is_online, message):
        """确认前状态检查完成"""
        if is_online:
            self.send_upgrade_command()
        else:
            if self.parent_window:
                self.parent_window.show_error("设备离线，操作失败")
            self.restore_buttons()
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
    
    def send_upgrade_command(self):
        """发送升级命令"""
        device_identify = self.selected_firmware.get('identifier', '')
        file_url = self.selected_firmware.get('download_url', '')
        
        if not file_url:
            if self.parent_window:
                self.parent_window.show_error("固件下载链接为空，无法升级")
            self.restore_buttons()
            return
        
        if self.device_query and self.device_query.token:
            self.upgrade_thread = UpgradeThread(
                self.sn,
                device_identify,
                file_url,
                self.device_query.token,
                self.device_query.host
            )
            self.upgrade_thread.finished_signal.connect(self.on_upgrade_finished)
            self.upgrade_thread.start()
        else:
            if self.parent_window:
                self.parent_window.show_error("无法获取访问令牌，操作失败")
            self.restore_buttons()
    
    def on_upgrade_finished(self, success, message):
        """升级命令发送完成"""
        if success:
            if self.parent_window:
                self.parent_window.show_success(f"升级命令已发送: {self.sn}")
            self.accept()
        else:
            if self.parent_window:
                self.parent_window.show_error(f"升级失败: {message}")
            self.restore_buttons()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
