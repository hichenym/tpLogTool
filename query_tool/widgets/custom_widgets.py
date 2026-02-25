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
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QCursor, QIcon
from query_tool.utils.config import (
    get_account_config, save_account_config,
    get_firmware_account_config, save_firmware_account_config
)
from query_tool.utils.device_query import DeviceQuery


def set_dark_title_bar(window):
    """设置深色标题栏（Windows 10/11）"""
    from query_tool.utils.logger import logger
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
    except Exception as e:
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
        except Exception as e2:
            logger.debug(f"设置深色标题栏失败: {e2}")


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


class BreathingLabel(QLabel):
    """呼吸闪烁标签（用于静默更新提示）"""
    def __init__(self, parent=None):
        super().__init__("●", parent)
        self.setStyleSheet("color: #888888; font-weight: bold; padding-right: 5px; font-size: 14px;")
        self._opacity = 1.0
        self._direction = -1  # -1 表示变暗，1 表示变亮
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_opacity)
        self._is_running = False
        self._current_color = "#888888"  # 当前颜色
        self._is_breathing = True  # 是否呼吸
    
    def setVisible(self, visible):
        """重写setVisible以控制定时器"""
        super().setVisible(visible)
        if visible and not self._is_running and self._is_breathing:
            # 显示时启动定时器，降低频率到 100ms
            self._timer.start(100)
            self._is_running = True
        elif not visible and self._is_running:
            # 隐藏时停止定时器
            self._timer.stop()
            self._is_running = False
    
    def _update_opacity(self):
        """更新透明度实现呼吸效果"""
        self._opacity += self._direction * 0.03  # 降低步长，使呼吸更慢
        
        # 反向改变方向
        if self._opacity >= 1.0:
            self._opacity = 1.0
            self._direction = -1
        elif self._opacity <= 0.4:
            self._opacity = 0.4
            self._direction = 1
        
        # 使用当前颜色，通过改变透明度来实现呼吸效果
        # 从十六进制颜色提取 RGB
        color_hex = self._current_color.lstrip('#')
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)
        
        # 应用透明度
        r_new = int(r * self._opacity)
        g_new = int(g * self._opacity)
        b_new = int(b * self._opacity)
        
        color_new = f"#{r_new:02x}{g_new:02x}{b_new:02x}"
        self.setStyleSheet(f"color: {color_new}; font-weight: bold; padding-right: 5px; font-size: 14px;")
    
    def set_color(self, color_hex: str, breathing: bool = True):
        """
        设置颜色并控制是否呼吸
        
        Args:
            color_hex: 颜色代码，如 "#888888"
            breathing: 是否呼吸闪烁
        """
        self._current_color = color_hex
        self._is_breathing = breathing
        
        if not breathing:
            # 停止呼吸，显示固定颜色
            if self._is_running:
                self._timer.stop()
                self._is_running = False
            self._opacity = 1.0
            self.setStyleSheet(f"color: {color_hex}; font-weight: bold; padding-right: 5px; font-size: 14px;")
        else:
            # 开始呼吸
            if self.isVisible() and not self._is_running:
                self._timer.start(100)
                self._is_running = True
    
    def stop(self):
        """停止呼吸动画"""
        if self._is_running:
            self._timer.stop()
            self._is_running = False
        self._is_breathing = False
        self.setStyleSheet(f"color: {self._current_color}; font-weight: bold; padding-right: 5px; font-size: 14px;")


class UpdateCheckSignals(QWidget):
    """更新检查信号发射器"""
    update_check_result = pyqtSignal(bool, object, str)  # (has_update, version_info, message)


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
    def __init__(self, parent=None, initial_tab=0):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(500, 480)  # 增加宽度和高度
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        # 保存父窗口引用，用于显示消息
        self.main_window = parent
        
        # 保存初始标签页索引
        self.initial_tab = initial_tab
        
        # 创建信号发射器
        self.update_signals = UpdateCheckSignals()
        self.update_signals.update_check_result.connect(self._on_update_check_result)
        
        # 加载设备账号配置
        self.env, self.device_username, self.device_password = get_account_config()
        self.env = 'pro'  # 固定使用生产环境
        
        # 加载固件账号配置
        self.firmware_username, self.firmware_password = get_firmware_account_config()
        
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
        """创建账号配置标签页（包含运维账号和固件账号）"""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(0)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
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
            is_device=True
        )
        scroll_layout.addWidget(device_group)
        
        # 固件账号组
        firmware_group = self.create_account_group(
            "固件账号",
            self.firmware_username,
            self.firmware_password,
            is_device=False
        )
        scroll_layout.addWidget(firmware_group)
        
        scroll_layout.addStretch()
        
        scroll_area.setWidget(scroll_content)
        tab_layout.addWidget(scroll_area)
        
        return tab
    
    def create_account_group(self, title, username, password, is_device=True):
        """创建账号配置组"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                color: #e0e0e0;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 10px;
                margin-bottom: 15px;
                padding-top: 15px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
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
            lambda: self.on_test_account_connection(username_input, password_input, is_device, test_btn)
        )
        action_layout.addWidget(test_btn)
        
        group_layout.addLayout(action_layout)
        
        # 保存输入框引用
        if is_device:
            self.device_username_input = username_input
            self.device_password_input = password_input
        else:
            self.firmware_username_input = username_input
            self.firmware_password_input = password_input
        
        return group
    
    def create_log_tab(self):
        """创建日志配置标签页"""
        from pathlib import Path
        
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(12)
        tab_layout.setContentsMargins(15, 15, 15, 10)
        
        # 文件日志复选框
        self.file_log_checkbox = QCheckBox("记录调试信息")
        self.file_log_checkbox.setChecked(self.enable_file_log)
        self.file_log_checkbox.stateChanged.connect(self.on_file_log_changed)
        tab_layout.addWidget(self.file_log_checkbox)
        
        # 获取实际的日志路径
        user_home = Path.home()
        log_dir = user_home / '.TPQueryTool' / 'logs'
        
        # 说明文本
        desc_label = QLabel(f"启用后，所有调试信息将输出到 {log_dir} 下的日志文件中。")
        desc_label.setStyleSheet("color: #909090; font-size: 11px;")
        desc_label.setWordWrap(True)
        tab_layout.addWidget(desc_label)
        
        tab_layout.addStretch()
        
        return tab

    def create_about_tab(self):
        """创建关于/更新标签页"""
        from query_tool.version import get_short_version, get_build_date_formatted
        from query_tool.utils.update_checker import UpdateChecker

        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(15)
        tab_layout.setContentsMargins(15, 15, 15, 10)

        # 版本信息组
        version_group = QGroupBox("版本信息")
        version_group.setStyleSheet("""
            QGroupBox {
                color: #e0e0e0;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 4px;
                margin-top: 10px;
                margin-bottom: 15px;
                padding-top: 15px;
                background-color: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
        """)

        version_layout = QVBoxLayout(version_group)
        version_layout.setSpacing(8)
        version_layout.setContentsMargins(15, 15, 15, 15)

        # 当前版本（双击显示详细信息）
        self.current_version_label = VersionLabel(f"当前版本：{get_short_version()}")
        self.current_version_label.setStyleSheet("color: #e0e0e0;")
        self.current_version_label.double_clicked = self.on_version_double_click
        
        # 保存版本信息用于切换显示
        self.short_version = get_short_version()
        self.build_date = get_build_date_formatted()
        self.show_detail = False
        
        version_layout.addWidget(self.current_version_label)

        tab_layout.addWidget(version_group)

        # 检查更新策略，决定是否显示更新检测组
        current_version = get_short_version().replace('V', '')
        checker = UpdateChecker(current_version)
        update_strategy = checker.should_auto_check()  # 获取更新策略
        
        # 从缓存加载版本信息以获取更新策略
        cached_info = checker._load_cache()
        if cached_info:
            update_strategy_str = cached_info.update_strategy
        else:
            update_strategy_str = 'prompt'  # 默认策略
        
        # 只有当更新策略不是 'silent' 时才显示更新检测组
        if update_strategy_str != 'silent':
            # 更新检测组
            update_group = QGroupBox("更新检测")
            update_group.setStyleSheet("""
                QGroupBox {
                    color: #e0e0e0;
                    font-size: 12px;
                    font-weight: bold;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    margin-top: 10px;
                    margin-bottom: 15px;
                    padding-top: 15px;
                    background-color: transparent;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    left: 10px;
                    padding: 0 5px;
                }
            """)

            update_layout = QVBoxLayout(update_group)
            update_layout.setSpacing(12)
            update_layout.setContentsMargins(15, 15, 15, 15)

            # 检查更新按钮
            self.check_update_btn_widget = QPushButton("检查更新")
            self.check_update_btn_widget.setFixedSize(120, 32)
            self.check_update_btn_widget.clicked.connect(self.on_check_update)
            update_layout.addWidget(self.check_update_btn_widget)

            tab_layout.addWidget(update_group)
        else:
            # 静默更新模式，不显示检查更新按钮
            self.check_update_btn_widget = None

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

    def on_check_update(self):
        """检查更新"""
        from PyQt5.QtWidgets import QApplication
        from query_tool.version import get_short_version
        from query_tool.utils.update_checker import UpdateChecker
        from query_tool.utils.logger import logger

        logger.info("用户点击检查更新按钮")

        # 检查按钮是否存在（静默更新模式下不存在）
        if not hasattr(self, 'check_update_btn_widget') or self.check_update_btn_widget is None:
            logger.warning("检查更新按钮不存在（可能是静默更新模式）")
            return

        # 禁用按钮
        self.check_update_btn_widget.setEnabled(False)
        self.check_update_btn_widget.setText("检查中...")
        logger.info("按钮已禁用，显示'检查中...'")

        # 禁用保存和取消按钮
        self.save_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        # 强制刷新UI
        QApplication.processEvents()

        try:
            # 获取当前版本（去掉V前缀）
            current_version = get_short_version().replace('V', '')
            logger.info(f"当前版本: {current_version}")

            # 创建更新检查器
            self.update_checker_temp = UpdateChecker(current_version)
            logger.info("更新检查器已创建")
            
            # 异步检查（强制刷新，忽略缓存）
            def callback(has_update, version_info, message):
                logger.info(f"检查更新回调: has_update={has_update}, message={message}")
                # 使用信号在主线程中处理结果
                self.update_signals.update_check_result.emit(has_update, version_info, message)
            
            logger.info("启动异步检查更新（强制刷新）")
            self.update_checker_temp.check_update_async_force_refresh(callback)

        except Exception as e:
            # 检查失败
            logger.error(f"检查更新失败: {e}", exc_info=True)

            if self.main_window and hasattr(self.main_window, 'show_error'):
                self.main_window.show_error(f"检查更新失败：{str(e)}")
            else:
                logger.error(f"无法显示错误消息: main_window={self.main_window}")
            
            self._restore_buttons()
    
    def _on_update_check_result(self, has_update, version_info, message):
        """处理更新检查结果"""
        from query_tool.version import get_short_version
        from query_tool.utils.logger import logger
        
        logger.info(f"处理更新检查结果: has_update={has_update}, message={message}")
        
        try:
            if has_update:
                # 有新版本，显示更新提示对话框
                current_version = get_short_version().replace('V', '')
                logger.info(f"发现新版本: {version_info.version}")
                
                if self.main_window:
                    if hasattr(self.main_window, 'show_update_prompt_dialog'):
                        logger.info("调用 show_update_prompt_dialog")
                        self.main_window.show_update_prompt_dialog(version_info, current_version)
                    else:
                        logger.error("main_window 没有 show_update_prompt_dialog 方法")
                else:
                    logger.error("main_window 为 None")
            else:
                # 已是最新版本
                logger.info(f"检查结果: {message}")
                
                if self.main_window:
                    if hasattr(self.main_window, 'show_success'):
                        logger.info("调用 show_success")
                        self.main_window.show_success("已是最新版本")
                    else:
                        logger.error("main_window 没有 show_success 方法")
                else:
                    logger.error("main_window 为 None")
        except Exception as e:
            logger.error(f"处理更新检查结果失败: {e}", exc_info=True)
        finally:
            self._restore_buttons()
    
    def _restore_buttons(self):
        """恢复按钮状态"""
        if hasattr(self, 'check_update_btn_widget') and self.check_update_btn_widget is not None:
            self.check_update_btn_widget.setEnabled(True)
            self.check_update_btn_widget.setText("检查更新")
        
        self.save_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)


    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        try:
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return date_str
        except:
            return date_str

    
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
    
    def on_test_account_connection(self, username_input, password_input, is_device, test_btn):
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
            if is_device:
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
            else:
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
