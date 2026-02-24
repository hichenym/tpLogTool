"""
端口穿透对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QLineEdit, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon
from .custom_widgets import set_dark_title_bar
from query_tool.utils.logger import logger
from query_tool.utils.session_manager import SessionManager
from query_tool.utils.thread_manager import ThreadManager
import json


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


class PortMappingThread(QThread):
    """端口穿透命令发送线程"""
    finished_signal = pyqtSignal(bool, str, str)  # success, message, data
    
    def __init__(self, sn, ip, port, token, host):
        super().__init__()
        self.sn = sn
        self.ip = ip
        self.port = port
        self.token = token
        self.host = host
    
    def run(self):
        try:
            session = SessionManager().get_session()
            url = f"https://{self.host}/api/seetong-siot-device/console/device/operate/sendCommand"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": self.token,
            }
            
            params_dict = {
                "ip": self.ip,
                "port": self.port
            }
            params_json = json.dumps(params_dict)
            
            data = {
                "code": "portmapDebug",
                "params": params_json,
                "sn": self.sn,
                "sourceType": "1"
            }
            
            response = session.post(url, json=data, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and result.get('success'):
                    data_value = result.get('data', '')
                    self.finished_signal.emit(True, "端口穿透成功", data_value)
                elif result.get('code') == 20001:
                    self.finished_signal.emit(False, "设备不在线，操作失败", "")
                else:
                    msg = result.get('msg', '操作失败')
                    self.finished_signal.emit(False, msg, "")
            else:
                self.finished_signal.emit(False, f"HTTP {response.status_code}", "")
        except Exception as e:
            logger.error(f"端口穿透出错: {e}")
            self.finished_signal.emit(False, f"端口穿透出错: {str(e)}", "")


class PortMappingDialog(QDialog):
    """端口穿透对话框"""
    
    def __init__(self, sn, dev_id, device_name, device_query, parent=None):
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_name = device_name
        self.device_query = device_query
        self.parent_window = parent
        
        # 状态
        self.is_online = False
        
        # 线程管理器
        self.thread_mgr = ThreadManager()
        
        self.init_ui()
        
        # 初始化：查询在线状态
        self.query_status()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("端口穿透")
        self.setFixedSize(500, 280)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 设备信息
        info_label = QLabel(f"设备: {self.device_name}    SN: {self.sn}")
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
        
        # 端口穿透设置分组
        settings_group = QGroupBox("端口穿透设置")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(15, 20, 15, 15)
        settings_layout.setSpacing(15)
        
        # IP地址输入
        ip_layout = QHBoxLayout()
        ip_layout.setSpacing(10)
        
        ip_label = QLabel("IP地址:")
        ip_label.setFixedWidth(70)
        ip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("例如: 192.168.11.1")
        self.ip_input.setFixedHeight(28)
        self.ip_input.textChanged.connect(self.on_ip_changed)  # 连接文本变化信号
        
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        
        settings_layout.addLayout(ip_layout)
        
        # 端口输入
        port_layout = QHBoxLayout()
        port_layout.setSpacing(10)
        
        port_label = QLabel("端口:")
        port_label.setFixedWidth(70)
        port_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("例如: 1111")
        self.port_input.setFixedHeight(28)
        self.port_input.textChanged.connect(self.on_port_changed)  # 连接文本变化信号
        
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        
        settings_layout.addLayout(port_layout)
        
        layout.addWidget(settings_group)
        
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
            thread = StatusQueryThread(self.sn, self.device_query.token)
            thread.finished_signal.connect(self.on_status_query_finished)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("status_query", thread)
            thread.start()
        else:
            self.status_label.setText("● 查询失败")
            self.status_label.setStyleSheet("color: #909090; font-size: 12px;")
    
    def on_status_query_finished(self, is_online, message):
        """状态查询完成"""
        self.is_online = is_online
        
        if is_online:
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
            self.confirm_btn.setEnabled(True)
        else:
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
            self.confirm_btn.setEnabled(False)
        
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
    
    def on_refresh(self):
        """刷新状态"""
        self.query_status()
    
    def on_wake(self):
        """唤醒设备"""
        self.status_label.setText("● 唤醒中...")
        self.status_label.setStyleSheet("color: #FFA500; font-size: 12px;")
        
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
            self.status_label.setText("● 在线")
            self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
            self.confirm_btn.setEnabled(True)
        else:
            if self.is_online:
                self.status_label.setText("● 在线")
                self.status_label.setStyleSheet("color: #00FF00; font-size: 12px;")
            else:
                self.status_label.setText("● 离线")
                self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
            self.confirm_btn.setEnabled(self.is_online)
    
    def on_ip_changed(self, text):
        """IP地址输入变化时实时校验"""
        text = text.strip()
        if not text:
            # 空值时恢复默认样式
            self.ip_input.setStyleSheet("")
            return
        
        # 验证IP地址格式
        if self.validate_ip(text):
            # 格式正确，恢复默认样式
            self.ip_input.setStyleSheet("")
        else:
            # 格式错误，显示红色边框
            self.ip_input.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #FF0000;
                    border-radius: 3px;
                    padding: 4px;
                }
            """)
    
    def on_port_changed(self, text):
        """端口输入变化时实时校验"""
        text = text.strip()
        if not text:
            # 空值时恢复默认样式
            self.port_input.setStyleSheet("")
            return
        
        # 验证端口格式和范围
        if text.isdigit():
            port_num = int(text)
            if 1 <= port_num <= 65535:
                # 格式正确，恢复默认样式
                self.port_input.setStyleSheet("")
            else:
                # 端口超出范围，显示红色边框
                self.port_input.setStyleSheet("""
                    QLineEdit {
                        border: 1px solid #FF0000;
                        border-radius: 3px;
                        padding: 4px;
                    }
                """)
        else:
            # 不是数字，显示红色边框
            self.port_input.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #FF0000;
                    border-radius: 3px;
                    padding: 4px;
                }
            """)
    
    def on_confirm(self):
        """确认端口穿透"""
        # 获取输入值
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()
        
        # 验证输入
        if not ip:
            if self.parent_window:
                self.parent_window.show_warning("请输入IP地址")
            return
        
        if not port:
            if self.parent_window:
                self.parent_window.show_warning("请输入端口")
            return
        
        # 验证IP地址格式
        if not self.validate_ip(ip):
            if self.parent_window:
                self.parent_window.show_warning("IP地址格式不正确，请输入有效的IPv4地址（例如：192.168.1.1）")
            return
        
        # 验证端口是否为数字
        if not port.isdigit():
            if self.parent_window:
                self.parent_window.show_warning("端口必须为数字")
            return
        
        # 验证端口范围（1-65535）
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            if self.parent_window:
                self.parent_window.show_warning("端口号必须在 1-65535 之间")
            return
        
        # 禁用所有按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 重新查询状态
        if self.device_query and not self.device_query.init_error:
            thread = StatusQueryThread(self.sn, self.device_query.token)
            thread.finished_signal.connect(
                lambda is_online, msg: self.on_confirm_status_checked(is_online, msg, ip, port)
            )
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("confirm_status_query", thread)
            thread.start()
        else:
            if self.parent_window:
                self.parent_window.show_error("查询状态失败，操作取消")
            self.restore_buttons()
    
    def validate_ip(self, ip):
        """验证IP地址格式"""
        import re
        # IPv4地址正则表达式
        pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return re.match(pattern, ip) is not None
    
    def on_confirm_status_checked(self, is_online, message, ip, port):
        """确认前状态检查完成"""
        if is_online:
            self.send_port_mapping_command(ip, port)
        else:
            if self.parent_window:
                self.parent_window.show_error("设备离线，操作失败")
            self.restore_buttons()
            self.status_label.setText("● 离线")
            self.status_label.setStyleSheet("color: #FF0000; font-size: 12px;")
    
    def send_port_mapping_command(self, ip, port):
        """发送端口穿透命令"""
        if self.device_query and self.device_query.token:
            thread = PortMappingThread(
                self.sn,
                ip,
                port,
                self.device_query.token,
                self.device_query.host
            )
            thread.finished_signal.connect(self.on_port_mapping_finished)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("port_mapping", thread)
            thread.start()
        else:
            if self.parent_window:
                self.parent_window.show_error("无法获取访问令牌，操作失败")
            self.restore_buttons()
    
    def on_port_mapping_finished(self, success, message, data):
        """端口穿透命令发送完成"""
        if success:
            if self.parent_window:
                self.parent_window.show_success(f"端口穿透命令发送成功: {self.sn}")
            self.accept()
        else:
            if self.parent_window:
                self.parent_window.show_error(f"端口穿透失败: {message}")
            self.restore_buttons()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
