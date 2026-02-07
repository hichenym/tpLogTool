"""
设备重启对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QButtonGroup, QWidget, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon
from .custom_widgets import set_dark_title_bar


class StatusQueryThread(QThread):
    """状态查询线程"""
    finished_signal = pyqtSignal(bool, str)  # is_online, message
    
    def __init__(self, sn, token):
        super().__init__()
        self.sn = sn
        self.token = token
    
    def run(self):
        """执行查询"""
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
        """执行唤醒"""
        try:
            from query_tool.utils import wake_device_smart
            
            # 使用智能唤醒：唤醒后自动检查在线状态
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


class RebootThread(QThread):
    """重启设备线程"""
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, sn, reboot_time, token, host):
        super().__init__()
        self.sn = sn
        self.reboot_time = reboot_time
        self.token = token
        self.host = host
    
    def run(self):
        """执行重启"""
        try:
            import json
            import requests
            
            url = f"https://{self.host}/api/seetong-siot-device/console/device/operate/sendCommand"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": self.token,
            }
            
            # 构建参数
            params_dict = {"reboot_time": self.reboot_time}
            params_json = json.dumps(params_dict)
            
            data = {
                "code": "reboot",
                "params": params_json,
                "sn": self.sn,
                "sourceType": "1"
            }
            
            response = requests.post(url, json=data, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and result.get('success'):
                    self.finished_signal.emit(True, "重启命令已发送")
                else:
                    msg = result.get('msg', '操作失败')
                    self.finished_signal.emit(False, msg)
            else:
                self.finished_signal.emit(False, f"HTTP {response.status_code}")
        except Exception as e:
            self.finished_signal.emit(False, f"重启出错: {str(e)}")


class RebootDialog(QDialog):
    """设备重启对话框"""
    
    def __init__(self, sn, dev_id, device_query, parent=None):
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_query = device_query
        self.is_online = False
        self.status_query_thread = None
        self.wake_thread = None
        self.reboot_thread = None
        
        self.init_ui()
        
        # 对话框打开时立即查询状态
        self.query_status()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设备重启")
        self.setFixedSize(450, 250)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 设备信息（设备名称和SN在一行，蓝色字体）
        # 获取设备名称
        device_name = "未知设备"
        if self.device_query and not self.device_query.init_error:
            try:
                device_name = self.device_query.get_device_name(self.dev_id)
                if not device_name:
                    device_name = "未命名设备"
            except:
                pass
        
        info_label = QLabel(f"设备: {device_name}    SN: {self.sn}")
        info_label.setStyleSheet("color: #4a9eff; font-size: 13px;")
        
        layout.addWidget(info_label)
        
        # 操作分组
        operation_group = QGroupBox("操作")
        operation_layout = QVBoxLayout(operation_group)
        operation_layout.setContentsMargins(15, 20, 15, 15)
        operation_layout.setSpacing(12)
        
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
        self.status_label.setFixedWidth(80)  # 固定宽度，防止文本变化时位置移动
        
        # 唤醒按钮（只显示图标）
        self.wake_btn = QPushButton()
        self.wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.wake_btn.setIconSize(QSize(16, 16))
        self.wake_btn.setFixedSize(28, 28)
        self.wake_btn.setEnabled(False)
        self.wake_btn.setToolTip("唤醒设备")
        self.wake_btn.clicked.connect(self.on_wake)
        
        # 刷新按钮
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("刷新状态")
        self.refresh_btn.clicked.connect(self.on_refresh)
        
        # 按钮样式（最小内边距）
        button_style = """
            QPushButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 0px;
                margin: 0px;
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
        status_layout.addSpacing(5)  # 固定间距
        status_layout.addWidget(self.wake_btn)
        status_layout.addSpacing(5)  # 固定间距
        status_layout.addWidget(self.refresh_btn)
        status_layout.addStretch()
        
        operation_layout.addWidget(status_widget)
        
        # 重启时间选择（与在线状态对齐）
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        time_label = QLabel("重启时间:")
        time_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        time_label.setFixedWidth(70)
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 垂直居中对齐
        
        self.radio_now = QRadioButton("立即重启")
        self.radio_now.setChecked(True)
        self.radio_now.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        
        self.radio_delay = QRadioButton("5分钟后重启")
        self.radio_delay.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.radio_now)
        self.button_group.addButton(self.radio_delay)
        
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.radio_now)
        time_layout.addWidget(self.radio_delay)
        time_layout.addStretch()
        
        operation_layout.addWidget(time_widget)
        
        layout.addWidget(operation_group)
        
        layout.addSpacing(15)
        
        # 操作按钮（右对齐）
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 确认/取消按钮样式（与固件对话框一致）
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
        
        # 禁用按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 启动查询线程
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
        
        # 启用按钮
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
    
    def on_refresh(self):
        """刷新状态"""
        self.query_status()
    
    def on_wake(self):
        """唤醒设备"""
        # 显示唤醒中状态
        self.status_label.setText("● 唤醒中...")
        self.status_label.setStyleSheet("color: #FFA500; font-size: 12px;")
        
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 启动唤醒线程
        self.wake_thread = WakeDeviceThread(self.dev_id, self.sn, self.device_query)
        self.wake_thread.finished_signal.connect(self.on_wake_finished)
        self.wake_thread.start()
    
    def on_wake_finished(self, success, message):
        """唤醒完成"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        
        # 唤醒完成后直接更新状态，不显示查询中
        if success:
            # 唤醒成功，设备在线
            self.is_online = True
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
        else:
            # 唤醒失败，恢复之前的状态显示
            if self.is_online:
                self.status_label.setText("● 在线")
                self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
            else:
                self.status_label.setText("● 离线")
                self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
    
    def on_confirm(self):
        """确认重启"""
        # 禁用所有按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 不显示查询中提示，直接后台查询
        # 重新查询状态
        if self.device_query and not self.device_query.init_error:
            self.status_query_thread = StatusQueryThread(self.sn, self.device_query.token)
            self.status_query_thread.finished_signal.connect(self.on_confirm_status_checked)
            self.status_query_thread.start()
        else:
            if self.parent():
                self.parent().show_error("查询状态失败，操作取消")
            self.restore_buttons()
    
    def on_confirm_status_checked(self, is_online, message):
        """确认前状态检查完成"""
        if is_online:
            # 设备在线，发送重启命令
            self.send_reboot_command()
        else:
            # 设备离线，提示并恢复按钮
            if self.parent():
                self.parent().show_error("设备离线，操作失败")
            self.restore_buttons()
            
            # 更新状态显示
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
    
    def send_reboot_command(self):
        """发送重启命令"""
        # 获取重启时间
        if self.radio_now.isChecked():
            reboot_time = "now"
        else:
            reboot_time = "after_five_minute"
        
        # 启动重启线程
        if self.device_query and self.device_query.token:
            self.reboot_thread = RebootThread(self.sn, reboot_time, self.device_query.token, self.device_query.host)
            self.reboot_thread.finished_signal.connect(self.on_reboot_finished)
            self.reboot_thread.start()
        else:
            if self.parent():
                self.parent().show_error("无法获取访问令牌，操作失败")
            self.restore_buttons()
    
    def on_reboot_finished(self, success, message):
        """重启命令发送完成"""
        if success:
            if self.parent():
                self.parent().show_success(f"重启命令已发送: {self.sn}")
            self.accept()
        else:
            if self.parent():
                self.parent().show_error(f"重启失败: {message}")
            self.restore_buttons()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
