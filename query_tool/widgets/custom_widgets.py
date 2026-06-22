"""
自定义控件
提供项目中使用的自定义Qt控件
"""
import os
import ctypes
from PyQt5.QtWidgets import (
    QLabel, QTextEdit, QLineEdit, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QFrame, QMessageBox, QTabWidget, QWidget,
    QScrollArea, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QCursor, QIcon
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.utils.config import (
    get_account_config, save_account_config,
    get_firmware_account_config, save_firmware_account_config,
    get_seetong_account_config, save_seetong_account_config,
)
from query_tool.utils.device_query import DeviceQuery
from query_tool.utils.style_manager import StyleManager
from query_tool.utils.theme_manager import t


def set_title_bar_theme(window, dark: bool = True):
    """设置标题栏深/浅色（Windows 10/11）"""
    try:
        hwnd = window.winId().__int__()
        value = ctypes.c_int(1 if dark else 0)
        for attr_id in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr_id, ctypes.byref(value), ctypes.sizeof(value)
                )
                return
            except Exception:
                continue
    except Exception:
        pass


def set_dark_title_bar(window):
    """向后兼容：根据当前主题设置标题栏"""
    from query_tool.utils.theme_manager import theme_manager
    set_title_bar_theme(window, dark=theme_manager.is_dark)


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


def prompt_configure_account(parent, title, text, initial_tab=0):
    """
    显示统一样式的账号配置提示框，并在确认后打开设置对话框。

    Args:
        parent: 父窗口
        title: 弹窗标题
        text: 弹窗内容
        initial_tab: 设置对话框初始标签页

    Returns:
        bool: 是否已打开设置对话框
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(QMessageBox.Question)
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)

    yes_btn = msg_box.button(QMessageBox.Yes)
    no_btn = msg_box.button(QMessageBox.No)

    if yes_btn:
        yes_btn.setText("")
        yes_btn.setIcon(QIcon(":/icons/common/ok.png"))
        yes_btn.setIconSize(QSize(20, 20))
        yes_btn.setFixedSize(60, 32)

    if no_btn:
        no_btn.setText("")
        no_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        no_btn.setIconSize(QSize(20, 20))
        no_btn.setFixedSize(60, 32)

    QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))

    if msg_box.exec_() != QMessageBox.Yes:
        return False

    dialog = SettingsDialog(parent, initial_tab=initial_tab)
    dialog.exec_()
    return True


class VersionLabel(QLabel):
    """版本标签，支持双击显示详细信息"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.double_clicked = None  # 双击事件回调
        
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件"""
        if event.button() == Qt.LeftButton and self.double_clicked:
            self.double_clicked()
        super().mouseDoubleClickEvent(event)


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


class SettingsDialog(AdaptiveDialog):
    """设置对话框"""
    def __init__(self, parent=None, initial_tab=0):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        # 保存父窗口引用，用于显示消息
        self.main_window = parent
        
        # 保存初始标签页索引
        self.initial_tab = initial_tab
        
        # 加载设备账号配置
        self.env, self.device_username, self.device_password = get_account_config()
        self.env = 'pro'  # 固定使用生产环境
        
        # 加载固件账号配置
        self.firmware_username, self.firmware_password = get_firmware_account_config()

        # 加载 Seetong 账号配置
        self.seetong_username, self.seetong_password = get_seetong_account_config()
        
        # 加载日志配置
        from query_tool.utils.config import get_log_config
        self.enable_file_log = get_log_config()
        
        self.init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
        
        # 设置初始标签页
        if hasattr(self, 'tab_widget') and hasattr(self, 'initial_tab'):
            self.tab_widget.setCurrentIndex(self.initial_tab)
        
    def init_ui(self):
        layout = self.init_dialog_layout(
            (500, 480),
            min_size=(420, 340),
            layout_margins=(15, 15, 15, 15),
            spacing=10,
        )
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(StyleManager.get_TAB_WIDGET())
        
        # 账号配置标签页
        account_tab = self.create_account_tab()
        self.tab_widget.addTab(account_tab, "账号配置")
        
        # 日志配置标签页
        log_tab = self.create_log_tab()
        self.tab_widget.addTab(log_tab, "日志配置")
        
        # 关于/更新标签页
        about_tab = self.create_about_tab()
        self.tab_widget.addTab(about_tab, "关于")
        
        layout.addWidget(self.tab_widget)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
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
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def create_account_tab(self):
        """创建账号配置标签页（包含运维、Seetong 和固件账号）"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(0)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(StyleManager.get_SCROLL_AREA())
        
        # 滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(0)
        scroll_layout.setContentsMargins(15, 15, 15, 15)
        
        # 运维账号组
        device_group = self.create_account_group(
            "运维账号",
            self.device_username,
            self.device_password,
            account_type="device"
        )
        scroll_layout.addWidget(device_group)
        
        # 固件账号组
        seetong_group = self.create_account_group(
            "Seetong账号",
            self.seetong_username,
            self.seetong_password,
            account_type="seetong"
        )
        scroll_layout.addWidget(seetong_group)

        firmware_group = self.create_account_group(
            "固件账号",
            self.firmware_username,
            self.firmware_password,
            account_type="firmware"
        )
        scroll_layout.addWidget(firmware_group)
        
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)
        
        return tab
    
    def create_account_group(self, title, username, password, account_type="device"):
        """创建账号配置组"""
        group = QGroupBox(title)
        group.setStyleSheet(StyleManager.get_GROUP_BOX())
        
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(12)
        group_layout.setContentsMargins(15, 15, 15, 15)
        
        # 账号输入
        username_layout = QHBoxLayout()
        username_label = QLabel("账号：")
        username_label.setFixedWidth(60)
        username_input = QLineEdit()
        username_input.setText(username)
        username_input.setPlaceholderText("请输入账号...")
        username_layout.addWidget(username_label)
        username_layout.addWidget(username_input)
        group_layout.addLayout(username_layout)
        
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
        group_layout.addLayout(password_layout)
        
        # 底部操作区域
        action_layout = QHBoxLayout()
        
        # 显示密码复选框
        show_password_checkbox = QCheckBox("显示密码")
        show_password_checkbox.stateChanged.connect(
            lambda state: self.on_show_password_changed(state, password_input)
        )
        action_layout.addWidget(show_password_checkbox)
        
        action_layout.addStretch()
        
        # 验证按钮
        test_btn = QPushButton("验证")
        test_btn.setFixedSize(90, 28)
        test_btn.clicked.connect(
            lambda: self.on_test_account_connection(username_input, password_input, account_type, test_btn)
        )
        action_layout.addWidget(test_btn)
        
        group_layout.addLayout(action_layout)
        
        # 保存输入框引用
        if account_type == "device":
            self.device_username_input = username_input
            self.device_password_input = password_input
        elif account_type == "firmware":
            self.firmware_username_input = username_input
            self.firmware_password_input = password_input
        else:
            self.seetong_username_input = username_input
            self.seetong_password_input = password_input
        
        return group
    
    def create_log_tab(self):
        """创建日志配置标签页"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(12)
        tab_layout.setContentsMargins(15, 15, 15, 10)
        
        # 文件日志复选框
        self.file_log_checkbox = QCheckBox("记录调试信息")
        self.file_log_checkbox.setChecked(self.enable_file_log)
        self.file_log_checkbox.stateChanged.connect(self.on_file_log_changed)
        tab_layout.addWidget(self.file_log_checkbox)
        
        tab_layout.addStretch()
        
        return tab

    def create_about_tab(self):
        """创建关于标签页。"""
        from query_tool.version import get_short_version, get_build_date_formatted

        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(15)
        tab_layout.setContentsMargins(15, 15, 15, 10)

        version_group = QGroupBox("版本信息")
        version_group.setStyleSheet(StyleManager.get_GROUP_BOX())

        version_layout = QVBoxLayout(version_group)
        version_layout.setSpacing(8)
        version_layout.setContentsMargins(15, 15, 15, 15)

        self.current_version_label = VersionLabel(f"当前版本：{get_short_version()}")
        self.current_version_label.setStyleSheet(f"color: {t('text_primary')};")
        self.current_version_label.double_clicked = self.on_version_double_click

        self.short_version = get_short_version()
        self.build_date = get_build_date_formatted()
        self.show_detail = False

        build_date_label = QLabel(f"编译日期：{self.build_date}")
        build_date_label.setStyleSheet(f"color: {t('text_secondary')};")

        version_layout.addWidget(self.current_version_label)
        version_layout.addWidget(build_date_label)
        tab_layout.addWidget(version_group)
        tab_layout.addStretch()
        return tab
    
    def on_version_double_click(self):
        """双击版本号切换显示详细信息"""
        self.show_detail = not self.show_detail
        
        if self.show_detail:
            # 显示详细信息：Vx.x.x (yyyyMMdd)
            # 从 "2026-02-24" 格式转换为 "20260224" 格式
            build_date_short = self.build_date.replace('-', '')
            self.current_version_label.setText(f"当前版本：{self.short_version} ({build_date_short})")
        else:
            # 只显示版本号
            self.current_version_label.setText(f"当前版本：{self.short_version}")

    def on_file_log_changed(self, state):
        """文件日志复选框状态改变"""
        from query_tool.utils.logger import logger
        from query_tool.utils.config import save_log_config
        
        enable = (state == Qt.Checked)
        
        # 实时生效
        if enable:
            logger.enable_file_log()
        else:
            logger.disable_file_log()
        
        # 保存配置
        save_log_config(enable)
        
        # 显示提示
        if self.main_window and hasattr(self.main_window, 'show_info'):
            if enable:
                self.main_window.show_info("文件日志已启用")
            else:
                self.main_window.show_info("文件日志已禁用")
    
    def on_show_password_changed(self, state, password_input):
        """显示/隐藏密码"""
        if state == Qt.Checked:
            password_input.setEchoMode(QLineEdit.Normal)
        else:
            password_input.setEchoMode(QLineEdit.Password)
    
    def on_test_account_connection(self, username_input, password_input, account_type, test_btn):
        """测试账号连接"""
        from PyQt5.QtWidgets import QApplication
        
        username = username_input.text().strip()
        password = password_input.text().strip()
        
        if not username or not password:
            if self.main_window and hasattr(self.main_window, 'show_warning'):
                self.main_window.show_warning("请输入账号和密码")
            return
        
        # 禁用按钮并更改状态
        test_btn.setEnabled(False)
        original_text = test_btn.text()
        test_btn.setText("验证中...")
        
        # 同时禁用保存和取消按钮，防止测试过程中关闭对话框
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 强制刷新UI，确保按钮状态立即显示
        QApplication.processEvents()
        
        try:
            if account_type == "device":
                # 测试运维账号
                if self.main_window and hasattr(self.main_window, 'show_progress'):
                    self.main_window.show_progress("正在测试运维账号连接...")
                
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
            elif account_type == "firmware":
                # 测试固件账号
                if self.main_window and hasattr(self.main_window, 'show_progress'):
                    self.main_window.show_progress("正在测试固件账号连接...")
                
                from query_tool.utils.firmware_api import test_firmware_login
                success, message = test_firmware_login(username, password)
                
                if success:
                    if self.main_window and hasattr(self.main_window, 'show_success'):
                        self.main_window.show_success("固件账号验证成功！")
                else:
                    if self.main_window and hasattr(self.main_window, 'show_error'):
                        self.main_window.show_error(f"固件账号连接失败：{message}")
            else:
                # 测试 Seetong 账号
                if self.main_window and hasattr(self.main_window, 'show_progress'):
                    self.main_window.show_progress("正在测试 Seetong 账号连接...")

                from query_tool.utils.siot_debug import validate_seetong_login
                success, message = validate_seetong_login(username, password)

                if success:
                    if self.main_window and hasattr(self.main_window, 'show_success'):
                        self.main_window.show_success("Seetong 账号验证成功！")
                else:
                    if self.main_window and hasattr(self.main_window, 'show_error'):
                        self.main_window.show_error(f"Seetong 账号连接失败：{message}")
        except Exception as e:
            if self.main_window and hasattr(self.main_window, 'show_error'):
                self.main_window.show_error(f"测试失败：{str(e)}")
        finally:
            # 恢复按钮状态
            test_btn.setEnabled(True)
            test_btn.setText(original_text)
            self.save_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)
    
    def on_save(self):
        """保存配置"""
        # 获取运维账号
        device_username = self.device_username_input.text().strip()
        device_password = self.device_password_input.text().strip()
        
        # 获取固件账号
        firmware_username = self.firmware_username_input.text().strip()
        firmware_password = self.firmware_password_input.text().strip()

        # 获取 Seetong 账号
        seetong_username = self.seetong_username_input.text().strip()
        seetong_password = self.seetong_password_input.text().strip()
        
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

        # 检查 Seetong 账号是否部分填写（只填了账号或只填了密码）
        if (seetong_username and not seetong_password) or (not seetong_username and seetong_password):
            if self.main_window and hasattr(self.main_window, 'show_warning'):
                self.main_window.show_warning("Seetong 账号和密码必须同时填写或同时为空")
            return
        
        # 保存运维账号到注册表（允许为空）
        env = 'pro'  # 固定使用生产环境
        device_saved = save_account_config(env, device_username, device_password)
        
        # 保存固件账号到注册表（允许为空）
        firmware_saved = save_firmware_account_config(firmware_username, firmware_password)

        # 保存 Seetong 账号到注册表（允许为空）
        seetong_saved = save_seetong_account_config(seetong_username, seetong_password)
        
        if device_saved and firmware_saved and seetong_saved:
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
                if not seetong_saved:
                    error_msg += "Seetong账号 "
                self.main_window.show_error(error_msg)

