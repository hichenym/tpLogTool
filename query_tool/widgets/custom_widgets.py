"""
自定义控件
提供项目中使用的自定义Qt控件
"""
import os
import ctypes
from PyQt5.QtWidgets import (
    QLabel, QTextEdit, QLineEdit, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QFrame, QMessageBox, QTabWidget, QWidget
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QCursor, QIcon
from query_tool.utils.config import (
    get_account_config, save_account_config,
    get_firmware_account_config, save_firmware_account_config
)
from query_tool.utils.device_query import DeviceQuery


def set_dark_title_bar(window):
    """设置深色标题栏（Windows 10/11）"""
    try:
        hwnd = window.winId().__int__()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
    except:
        try:
            # 尝试 Windows 10 的方式
            DWMWA_USE_IMMERSIVE_DARK_MODE = 19
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        except:
            pass


def show_message_box(parent, icon, title, text):
    """
    显示带深色标题栏的消息框
    
    Args:
        parent: 父窗口
        icon: 图标类型 (QMessageBox.Information, QMessageBox.Warning, QMessageBox.Critical)
        title: 标题
        text: 消息内容
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(icon)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(QMessageBox.Ok)
    
    # 延迟设置深色标题栏
    QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
    
    msg_box.exec_()


def show_question_box(parent, title, text):
    """
    显示带深色标题栏的询问对话框
    
    Args:
        parent: 父窗口
        title: 标题
        text: 消息内容
        
    Returns:
        QMessageBox.Yes 或 QMessageBox.No
    """
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.Yes)
    
    # 延迟设置深色标题栏
    QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
    
    return msg_box.exec_()


class ClickableLabel(QLabel):
    """可点击的标签，用于显示版本信息"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针为手型
        self.clicked = None  # 点击事件回调
        
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton and self.clicked:
            self.clicked()
        super().mousePressEvent(event)


class PlainTextEdit(QTextEdit):
    """纯文本输入框，粘贴时自动清除格式"""
    def insertFromMimeData(self, source):
        """重写粘贴方法，只插入纯文本"""
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)


class ClickableLineEdit(QLineEdit):
    """可双击打开目录的输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)  # 设置鼠标指针为手型
        
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.LeftButton:
            path = self.text().strip()
            if path and os.path.exists(path):
                # 在Windows上打开资源管理器
                try:
                    os.startfile(path)
                except Exception as e:
                    print(f"无法打开目录: {e}")
        super().mouseDoubleClickEvent(event)


class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("账号密码设置")
        self.setFixedSize(380, 240)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        # 保存父窗口引用，用于显示消息
        self.main_window = parent
        
        # 加载设备账号配置
        self.env, self.device_username, self.device_password = get_account_config()
        self.env = 'pro'  # 固定使用生产环境
        
        # 加载固件账号配置
        self.firmware_username, self.firmware_password = get_firmware_account_config()
        
        self.init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #e0e0e0;
                padding: 8px 20px;
                border: 1px solid #555555;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #505050;
                color: #e0e0e0;
                border-bottom: 1px solid #2b2b2b;
            }
            QTabBar::tab:hover {
                background-color: #4a4a4a;
                color: #e0e0e0;
            }
        """)
        
        # 运维账号标签页
        device_tab = self.create_account_tab(
            self.device_username, 
            self.device_password,
            is_device=True
        )
        self.tab_widget.addTab(device_tab, "运维账号")
        
        # 固件账号标签页
        firmware_tab = self.create_account_tab(
            self.firmware_username,
            self.firmware_password,
            is_device=False
        )
        self.tab_widget.addTab(firmware_tab, "固件账号")
        
        layout.addWidget(self.tab_widget)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setFixedSize(90, 32)
        self.test_btn.clicked.connect(self.on_test_connection)
        
        self.save_btn = QPushButton()
        self.save_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.save_btn.setIconSize(QSize(18, 18))
        self.save_btn.setFixedSize(60, 32)
        self.save_btn.clicked.connect(self.on_save)
        
        self.cancel_btn = QPushButton()
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(18, 18))
        self.cancel_btn.setFixedSize(60, 32)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.test_btn)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def create_account_tab(self, username, password, is_device=True):
        """创建账号配置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(12)
        tab_layout.setContentsMargins(15, 15, 15, 10)
        
        # 账号输入
        username_layout = QHBoxLayout()
        username_label = QLabel("账号：")
        username_label.setFixedWidth(60)
        username_input = QLineEdit()
        username_input.setText(username)
        username_input.setPlaceholderText("请输入账号...")
        username_layout.addWidget(username_label)
        username_layout.addWidget(username_input)
        tab_layout.addLayout(username_layout)
        
        # 密码输入
        password_layout = QHBoxLayout()
        password_label = QLabel("密码：")
        password_label.setFixedWidth(60)
        password_input = QLineEdit()
        password_input.setText(password)
        password_input.setPlaceholderText("请输入密码...")
        password_input.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(password_label)
        password_layout.addWidget(password_input)
        tab_layout.addLayout(password_layout)
        
        # 显示密码复选框
        show_password_checkbox = QCheckBox("显示密码")
        show_password_checkbox.stateChanged.connect(
            lambda state: self.on_show_password_changed(state, password_input)
        )
        tab_layout.addWidget(show_password_checkbox)
        
        tab_layout.addStretch()
        
        # 保存输入框引用
        if is_device:
            self.device_username_input = username_input
            self.device_password_input = password_input
        else:
            self.firmware_username_input = username_input
            self.firmware_password_input = password_input
        
        return tab
    
    def on_show_password_changed(self, state, password_input):
        """显示/隐藏密码"""
        if state == Qt.Checked:
            password_input.setEchoMode(QLineEdit.Normal)
        else:
            password_input.setEchoMode(QLineEdit.Password)
    
    def on_test_connection(self):
        """测试连接"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # 运维账号
            username = self.device_username_input.text().strip()
            password = self.device_password_input.text().strip()
            
            if not username or not password:
                if self.main_window and hasattr(self.main_window, 'show_warning'):
                    self.main_window.show_warning("请输入账号和密码")
                return
            
            # 禁用按钮
            self.test_btn.setEnabled(False)
            self.test_btn.setText("测试中...")
            self.save_btn.setEnabled(False)
            
            # 显示进度消息
            if self.main_window and hasattr(self.main_window, 'show_progress'):
                self.main_window.show_progress("正在测试运维账号连接...")
            
            try:
                # 尝试登录
                env = 'pro'  # 固定使用生产环境
                query = DeviceQuery(env, username, password, use_cache=False)
                if query.init_error:
                    if self.main_window and hasattr(self.main_window, 'show_error'):
                        self.main_window.show_error(f"运维账号连接失败：{query.init_error}")
                elif query.token:
                    if self.main_window and hasattr(self.main_window, 'show_success'):
                        self.main_window.show_success("运维账号验证成功！")
                else:
                    if self.main_window and hasattr(self.main_window, 'show_error'):
                        self.main_window.show_error("无法获取访问令牌，请检查账号密码")
            except Exception as e:
                if self.main_window and hasattr(self.main_window, 'show_error'):
                    self.main_window.show_error(f"测试失败：{str(e)}")
            finally:
                # 恢复按钮
                self.test_btn.setEnabled(True)
                self.test_btn.setText("测试连接")
                self.save_btn.setEnabled(True)
        
        else:  # 固件账号
            username = self.firmware_username_input.text().strip()
            password = self.firmware_password_input.text().strip()
            
            if not username or not password:
                if self.main_window and hasattr(self.main_window, 'show_warning'):
                    self.main_window.show_warning("请输入账号和密码")
                return
            
            # 禁用按钮
            self.test_btn.setEnabled(False)
            self.test_btn.setText("测试中...")
            self.save_btn.setEnabled(False)
            
            # 显示进度消息
            if self.main_window and hasattr(self.main_window, 'show_progress'):
                self.main_window.show_progress("正在测试固件账号连接...")
            
            try:
                # 测试固件登录
                from query_tool.utils.firmware_api import test_firmware_login
                success, message = test_firmware_login(username, password)
                
                if success:
                    if self.main_window and hasattr(self.main_window, 'show_success'):
                        self.main_window.show_success("固件账号验证成功！")
                else:
                    if self.main_window and hasattr(self.main_window, 'show_error'):
                        self.main_window.show_error(f"固件账号连接失败：{message}")
            except Exception as e:
                if self.main_window and hasattr(self.main_window, 'show_error'):
                    self.main_window.show_error(f"测试失败：{str(e)}")
            finally:
                # 恢复按钮
                self.test_btn.setEnabled(True)
                self.test_btn.setText("测试连接")
                self.save_btn.setEnabled(True)
    
    def on_save(self):
        """保存配置"""
        # 获取运维账号
        device_username = self.device_username_input.text().strip()
        device_password = self.device_password_input.text().strip()
        
        # 获取固件账号
        firmware_username = self.firmware_username_input.text().strip()
        firmware_password = self.firmware_password_input.text().strip()
        
        # 检查运维账号是否部分填写（只填了账号或只填了密码）
        if (device_username and not device_password) or (not device_username and device_password):
            if self.main_window and hasattr(self.main_window, 'show_warning'):
                self.main_window.show_warning("运维账号和密码必须同时填写或同时为空")
            return
        
        # 检查固件账号是否部分填写（只填了账号或只填了密码）
        if (firmware_username and not firmware_password) or (not firmware_username and firmware_password):
            if self.main_window and hasattr(self.main_window, 'show_warning'):
                self.main_window.show_warning("固件账号和密码必须同时填写或同时为空")
            return
        
        # 保存运维账号到注册表（允许为空）
        env = 'pro'  # 固定使用生产环境
        device_saved = save_account_config(env, device_username, device_password)
        
        # 保存固件账号到注册表（允许为空）
        firmware_saved = save_firmware_account_config(firmware_username, firmware_password)
        
        if device_saved and firmware_saved:
            if self.main_window and hasattr(self.main_window, 'show_success'):
                self.main_window.show_success("配置已保存！")
            self.accept()
        else:
            if self.main_window and hasattr(self.main_window, 'show_error'):
                error_msg = "保存失败："
                if not device_saved:
                    error_msg += "运维账号 "
                if not firmware_saved:
                    error_msg += "固件账号 "
                self.main_window.show_error(error_msg)
