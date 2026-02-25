import sys
import os

# 添加项目根目录到 Python 路径（支持直接运行 main.py）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 禁止生成 __pycache__ 和 .pyc 文件
sys.dont_write_bytecode = True

import ctypes
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QStackedWidget, QDesktopWidget
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon
import requests

# 导入资源文件
import resources.icon_res as icon_res

# 导入版本信息
from query_tool.version import get_version_string

# 导入页面
from query_tool.pages import PageRegistry
# 导入pages模块以触发页面注册
from query_tool import pages

# 导入工具和控件
from query_tool.utils import config_manager
from query_tool.widgets import SettingsDialog

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()


def set_dark_title_bar(window):
    """设置深色标题栏（Windows 10/11）"""
    try:
        hwnd = window.winId().__int__()
        
        # Windows 10 版本 1809 及以上支持深色标题栏
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 1903+)
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 19 (Windows 10 1809)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        # 尝试使用 Windows 11 的方式
        try:
            value = ctypes.c_int(1)  # 1 = 深色模式
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        except Exception as e:
            logger.debug(f"设置深色标题栏失败（Windows 11方式）: {e}")
            # 如果失败，尝试 Windows 10 的方式
            DWMWA_USE_IMMERSIVE_DARK_MODE = 19
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
    except Exception as e:
        print(f"设置深色标题栏失败: {e}")


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("查询工具")
        self.setGeometry(100, 100, 1080, 680)
        self.setMinimumSize(600, 450)
        self.setWindowIcon(QIcon(":/icons/app/logo.png"))
        
        # 页面实例
        self.pages = []
        self.page_buttons = []
        
        # 更新管理器
        self.update_manager = None
        self.pending_update_file = None  # 待安装的更新文件
        
        self.init_ui()
        self.load_config()
        self.center_on_screen()
        
        # 设置深色标题栏（需要在窗口显示后调用）
        QTimer.singleShot(0, lambda: set_dark_title_bar(self))
        
        # 启动时检查更新
        QTimer.singleShot(2000, self.check_update_on_startup)
    
    def init_ui(self):
        """初始化UI"""
        # 创建自定义菜单栏
        menu_widget = QWidget()
        menu_widget.setFixedHeight(28)
        menu_widget.setAutoFillBackground(True)  # 确保使用自定义背景
        from query_tool.utils import StyleManager
        StyleManager.apply_to_widget(menu_widget, "MENU_BAR")
        menu_layout = QHBoxLayout(menu_widget)
        menu_layout.setContentsMargins(5, 0, 0, 0)
        menu_layout.setSpacing(0)
        
        # 从注册表获取所有页面并创建按钮
        for page_config in PageRegistry.get_all_pages():
            page_class = page_config['class']
            page_name = page_config['name']
            page_icon = page_config.get('icon')
            
            # 创建页面实例
            page = page_class(self)
            self.pages.append(page)
            
            # 创建菜单按钮
            btn = QPushButton(page_name)
            btn.setCheckable(True)
            
            # 如果有图标，设置图标
            if page_icon:
                btn.setIcon(QIcon(page_icon))
                btn.setIconSize(QSize(16, 16))
            
            StyleManager.apply_to_widget(btn, "MENU_BUTTON")
            btn.clicked.connect(lambda checked, idx=len(self.pages)-1: self.switch_page(idx))
            self.page_buttons.append(btn)
            menu_layout.addWidget(btn)
        
        # 设置按钮
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon(":/icons/system/setting.png"))
        self.settings_btn.setIconSize(QSize(18, 18))
        self.settings_btn.setFixedSize(32, 28)
        self.settings_btn.setToolTip("设置")
        StyleManager.apply_to_widget(self.settings_btn, "SETTINGS_BUTTON")
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        
        menu_layout.addStretch()
        menu_layout.addWidget(self.settings_btn)
        menu_layout.addSpacing(5)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 添加菜单栏
        main_layout.addWidget(menu_widget)
        
        # 创建堆叠窗口部件
        self.stacked_widget = QStackedWidget()
        for page in self.pages:
            self.stacked_widget.addWidget(page)
            # 连接页面的状态消息信号
            page.status_message.connect(self.on_page_status_message)
        
        main_layout.addWidget(self.stacked_widget)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态消息标签（支持富文本）- 左侧
        from PyQt5.QtWidgets import QLabel
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setStyleSheet("color: #e0e0e0; padding-left: 5px;")
        self.status_bar.addWidget(self.status_label, 1)
        
        # 下载进度标签 - 右侧
        self.download_progress_label = QLabel("")
        self.download_progress_label.setStyleSheet("color: #4a9eff; padding-right: 10px;")
        self.download_progress_label.setVisible(False)  # 默认隐藏
        self.status_bar.addPermanentWidget(self.download_progress_label)
        
        self.status_bar.showMessage("就绪")
        self.show_info("就绪")
        
        # 加载上次选择的页面
        app_config = config_manager.load_app_config()
        page_index = app_config.last_page_index
        if 0 <= page_index < len(self.pages):
            self.switch_page(page_index)
        else:
            self.switch_page(0)
    
    def switch_page(self, index):
        """切换页面"""
        from query_tool.utils.logger import logger
        
        if index < 0 or index >= len(self.pages):
            return
        
        page_names = ["设备状态", "固件管理", "GitLab日志"]
        page_name = page_names[index] if index < len(page_names) else f"页面{index}"
        logger.debug(f"切换到页面: {page_name}")
        
        self.stacked_widget.setCurrentIndex(index)
        
        # 更新按钮选中状态
        for i, btn in enumerate(self.page_buttons):
            btn.setChecked(i == index)
        
        # 调用页面的显示事件
        self.pages[index].on_page_show()
        
        # 保存当前页面索引
        app_config = config_manager.load_app_config()
        app_config.last_page_index = index
        config_manager.save_app_config(app_config)
    
    def on_settings_clicked(self):
        """设置按钮点击"""
        dialog = SettingsDialog(self)
        dialog.exec_()
    
    def on_page_status_message(self, message, msg_type, timeout):
        """处理页面状态消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        
        # 将字符串类型转换为枚举
        type_map = {
            "info": MessageType.INFO,
            "success": MessageType.SUCCESS,
            "warning": MessageType.WARNING,
            "error": MessageType.ERROR,
            "progress": MessageType.PROGRESS
        }
        
        message_type = type_map.get(msg_type, MessageType.INFO)
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, message_type, timeout if timeout > 0 else None)
    
    def show_info(self, message, duration=2000):
        """显示信息消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.INFO, duration)
    
    def show_success(self, message, duration=3000):
        """显示成功消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.SUCCESS, duration)
    
    def show_error(self, message, duration=5000):
        """显示错误消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.ERROR, duration)
    
    def center_on_screen(self):
        """将窗口居中显示"""
        screen = QDesktopWidget().screenGeometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    def load_config(self):
        """加载配置"""
        for page in self.pages:
            if hasattr(page, 'load_config'):
                page.load_config()
    
    def save_config(self):
        """保存配置"""
        for page in self.pages:
            if hasattr(page, 'save_config'):
                page.save_config()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        from query_tool.utils.logger import logger
        
        # 检查是否正在下载
        if self.update_manager and hasattr(self.update_manager, 'downloader'):
            if self.update_manager.downloader.download_thread and \
               self.update_manager.downloader.download_thread.isRunning():
                logger.info("检测到正在下载更新，取消下载...")
                self.update_manager.cancel_download()
                # 隐藏下载进度标签
                self.download_progress_label.setVisible(False)
        
        # 保存配置
        self.save_config()
        
        # 清理资源
        for page in self.pages:
            if hasattr(page, 'cleanup'):
                page.cleanup()
        
        # 如果有待安装的更新（silent 策略），在关闭时安装
        if self.pending_update_file:
            try:
                from query_tool.utils.update_downloader import UpdateInstaller
                
                logger.info("检测到待安装的更新，准备静默安装...")
                UpdateInstaller.apply_update(self.pending_update_file, restart=True)
                # 如果执行到这里说明更新失败，继续正常关闭
            except Exception as e:
                logger.error(f"静默更新失败: {e}")
        
        event.accept()
    
    def check_update_on_startup(self):
        """启动时检查更新"""
        try:
            from query_tool.utils.update_manager import UpdateManager
            from query_tool.version import get_short_version
            from query_tool.utils.logger import logger
            
            # 获取当前版本号（去掉 V 前缀）
            current_version = get_short_version().replace('V', '')
            
            # 创建更新管理器
            self.update_manager = UpdateManager(current_version, self)
            
            # 检查是否应该自动检查更新
            if not self.update_manager.should_auto_check():
                logger.info("更新策略为 manual，跳过自动检查")
                return
            
            # 连接信号
            self.update_manager.update_available.connect(self.on_update_available)
            self.update_manager.download_progress.connect(self.on_download_progress)
            self.update_manager.download_finished.connect(self.on_download_finished)
            
            # 异步检查更新
            logger.info("开始检查更新...")
            self.update_manager.check_update_async()
            
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"检查更新失败: {e}")
    
    def on_update_available(self, version_info):
        """发现新版本"""
        from query_tool.utils.logger import logger
        from query_tool.version import get_short_version
        
        logger.info(f"发现新版本: {version_info}")
        
        strategy = version_info.update_strategy
        current_version = get_short_version().replace('V', '')
        
        if strategy == 'prompt':
            # 提示更新：显示对话框
            self.show_update_prompt_dialog(version_info, current_version)
        
        elif strategy == 'silent':
            # 静默更新：后台下载
            logger.info("静默更新模式，开始后台下载...")
            self.show_info("正在后台下载更新...", 3000)
            self.update_manager.download_update(version_info)
    
    def show_update_prompt_dialog(self, version_info, current_version):
        """显示更新提示对话框"""
        from query_tool.widgets.update_dialog import UpdatePromptDialog
        from query_tool.utils.logger import logger
        
        dialog = UpdatePromptDialog(version_info, current_version, self)
        
        # 连接信号
        dialog.update_now.connect(lambda: self.start_download_update(version_info))
        dialog.remind_later.connect(lambda: logger.info("用户选择稍后提醒"))
        dialog.skip_version.connect(lambda: self.on_skip_version(version_info))
        
        dialog.exec_()
    
    def on_skip_version(self, version_info):
        """处理跳过版本"""
        from query_tool.utils.logger import logger
        
        logger.info(f"用户跳过版本 {version_info.version}")
        
        # 记录跳过的版本
        if self.update_manager:
            self.update_manager.skip_version(version_info.version)
            self.show_info(f"已跳过版本 V{version_info.version}，下次不再提示", 3000)
    
    def start_download_update(self, version_info):
        """开始下载更新"""
        from query_tool.utils.logger import logger
        
        logger.info(f"开始下载更新: {version_info.version}")
        
        # 在右下角显示下载开始
        self.download_progress_label.setText(f"正在下载更新 V{version_info.version}...")
        self.download_progress_label.setVisible(True)
        
        # 开始下载
        self.update_manager.download_update(version_info)
    
    def on_download_progress(self, downloaded, total):
        """下载进度更新"""
        if total > 0:
            progress = int((downloaded / total) * 100)
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            # 在右下角显示下载进度
            self.download_progress_label.setText(
                f"下载更新: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress}%)"
            )
            self.download_progress_label.setVisible(True)
    
    def on_download_finished(self, success, result):
        """下载完成"""
        from query_tool.utils.logger import logger
        
        if success:
            logger.info(f"下载完成: {result}")
            
            # 隐藏下载进度标签
            self.download_progress_label.setVisible(False)
            
            strategy = self.update_manager.get_update_strategy()
            
            if strategy == 'prompt':
                # 提示模式：显示下载完成消息，然后弹出重启对话框
                self.show_success("更新下载完成", 2000)
                
                # 检查是否在开发环境
                import sys
                if not getattr(sys, 'frozen', False):
                    # 开发环境，显示提示
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(
                        self,
                        "开发环境提示",
                        "更新已下载完成。\n\n"
                        "注意：自动更新功能仅在打包后的程序中可用。\n\n"
                        "当前运行在开发环境，无法执行自动更新。\n"
                        "如需测试更新功能，请使用以下命令打包：\n\n"
                        "python scripts/build.py"
                    )
                    return
                
                # 延迟显示重启对话框，让用户看到成功消息
                QTimer.singleShot(500, self.show_update_complete_dialog)
            
            elif strategy == 'silent':
                # 静默模式：保存文件路径，等待程序关闭时安装
                self.pending_update_file = result
                logger.info("静默更新已下载，将在程序关闭时安装")
                self.show_success("更新已下载，将在下次启动时自动安装", 5000)
        
        else:
            logger.error(f"下载失败: {result}")
            
            # 隐藏下载进度标签
            self.download_progress_label.setVisible(False)
            
            self.show_error(f"下载更新失败: {result}", 5000)
    
    def show_update_complete_dialog(self):
        """显示更新完成对话框"""
        from query_tool.widgets.update_dialog import UpdateCompleteDialog
        from query_tool.utils.logger import logger
        
        if not self.update_manager.latest_version_info:
            return
        
        dialog = UpdateCompleteDialog(self.update_manager.latest_version_info, self)
        
        # 连接信号
        dialog.restart_now.connect(self.apply_update_and_restart)
        dialog.restart_later.connect(lambda: logger.info("用户选择稍后重启"))
        
        dialog.exec_()
    
    def apply_update_and_restart(self):
        """应用更新并重启"""
        from query_tool.utils.logger import logger
        from PyQt5.QtWidgets import QMessageBox
        
        try:
            logger.info("用户选择立即重启，应用更新...")
            
            # 检查是否有下载的文件
            if not self.update_manager.downloaded_file_path:
                error_msg = "没有找到下载的更新文件"
                logger.error(error_msg)
                QMessageBox.warning(self, "更新失败", error_msg)
                return
            
            # 检查文件是否存在
            import os
            if not os.path.exists(self.update_manager.downloaded_file_path):
                error_msg = f"更新文件不存在: {self.update_manager.downloaded_file_path}"
                logger.error(error_msg)
                QMessageBox.warning(self, "更新失败", error_msg)
                return
            
            logger.info(f"更新文件路径: {self.update_manager.downloaded_file_path}")
            
            # 应用更新
            self.update_manager.apply_update(restart=True)
            
            # 如果执行到这里，说明是开发环境或更新失败
            logger.warning("更新未执行（可能是开发环境）")
            
        except RuntimeError as e:
            # 开发环境错误（预期的）
            error_msg = str(e)
            logger.warning(error_msg)
            QMessageBox.information(
                self,
                "开发环境提示",
                f"{error_msg}\n\n"
                "自动更新功能仅在打包后的程序中可用。\n\n"
                "如需测试更新功能，请使用以下命令打包：\n"
                "python scripts/build.py"
            )
        except Exception as e:
            logger.error(f"应用更新失败: {e}", exc_info=True)
            QMessageBox.critical(
                self, 
                "更新失败", 
                f"应用更新时发生错误：\n\n{str(e)}\n\n请查看日志文件获取详细信息。"
            )
            self.show_error(f"应用更新失败: {e}", 5000)


def main():
    """主函数入口"""
    # 设置全局异常处理
    from query_tool.utils.logger import logger, setup_exception_handler
    from query_tool.version import get_version_string
    import platform
    
    setup_exception_handler()
    
    # 记录程序启动信息
    logger.info(f"程序启动: {get_version_string()}")
    logger.info(f"Python版本: {sys.version.split()[0]}")
    logger.info(f"操作系统: {platform.system()} {platform.release()}")
    
    try:
        app = QApplication(sys.argv)
        
        # 设置全局深色主题
        app.setStyleSheet("""
        /* 全局样式 */
        QWidget {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }
        
        /* 输入框样式 */
        QTextEdit, QPlainTextEdit, QLineEdit {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
            selection-background-color: #505050;
        }
        QTextEdit:disabled, QPlainTextEdit:disabled, QLineEdit:disabled {
            background-color: #2b2b2b;
            color: #606060;
            border: 1px solid #3c3c3c;
        }
        
        /* 下拉框样式 */
        QComboBox {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
            padding-right: 0px;
        }
        QComboBox:hover {
            border: 1px solid #555555;
        }
        QComboBox:disabled {
            background-color: #2b2b2b;
            color: #606060;
            border: 1px solid #3c3c3c;
        }
        QComboBox::drop-down {
            border: none;
            background-color: #505050;
            width: 24px;
            margin: 0px;
            padding: 0px;
            border-left: 1px solid #555555;
        }
        QComboBox::drop-down:disabled {
            background-color: #3c3c3c;
            border-left: 1px solid #3c3c3c;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0px;
        }
        QComboBox QAbstractItemView {
            background-color: #3c3c3c;
            color: #e0e0e0;
            selection-background-color: #505050;
            border: 1px solid #555555;
        }
        
        /* 日期选择器样式 */
        QDateEdit {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
        }
        QDateEdit:hover {
            border: 1px solid #555555;
        }
        QDateEdit:disabled {
            background-color: #2b2b2b;
            color: #606060;
            border: 1px solid #3c3c3c;
        }
        QDateEdit::drop-down {
            border: none;
            background-color: #505050;
        }
        QDateEdit::drop-down:disabled {
            background-color: #3c3c3c;
        }
        QDateEdit QAbstractItemView {
            background-color: #3c3c3c;
            color: #e0e0e0;
            selection-background-color: #505050;
            border: 1px solid #555555;
        }
        QCalendarWidget {
            background-color: #3c3c3c;
            color: #e0e0e0;
        }
        QCalendarWidget QToolButton {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
        }
        QCalendarWidget QMenu {
            background-color: #3c3c3c;
            color: #e0e0e0;
        }
        QCalendarWidget QSpinBox {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
        }
        QCalendarWidget QWidget {
            alternate-background-color: #404040;
        }
        QCalendarWidget QAbstractItemView:enabled {
            background-color: #3c3c3c;
            color: #e0e0e0;
            selection-background-color: #505050;
        }
        
        /* 按钮样式 */
        QPushButton {
            background-color: #3c3c3c;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border: 1px solid #555555;
        }
        QPushButton:pressed {
            background-color: #505050;
        }
        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #707070;
            border: 1px solid #3c3c3c;
        }
        
        /* 复选框样式 */
        QCheckBox {
            color: #e0e0e0;
            spacing: 5px;
        }
        QCheckBox:disabled {
            color: #606060;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #404040;
        }
        QCheckBox::indicator:hover {
            border: 1px solid #555555;
        }
        QCheckBox::indicator:checked {
            background-color: #0d7377;
            border: 1px solid #0d7377;
        }
        QCheckBox::indicator:disabled {
            background-color: #2b2b2b;
            border: 1px solid #3c3c3c;
        }
        QCheckBox::indicator:checked:disabled {
            background-color: #0a5a5d;
            border: 1px solid #0a5a5d;
        }
        
        /* 标签样式 */
        QLabel {
            color: #e0e0e0;
            background-color: transparent;
        }
        
        /* 状态栏样式 */
        QStatusBar {
            background-color: #2b2b2b;
            color: #e0e0e0;
            border-top: 1px solid #3c3c3c;
            border-right: none;
            border-bottom: none;
            border-left: none;
        }
        QStatusBar::item {
            border: none;
        }
        QStatusBar QLabel {
            border: none;
        }
        
        /* 表格角落按钮样式（左上角空白单元格） */
        QTableCornerButton::section {
            background-color: #2b2b2b;
            border: 1px solid #555555;
        }
        
        /* 滚动条样式 */
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 12px;
            border: none;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 6px;
            min-height: 20px;
            margin: 2px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #6a6a6a;
        }
        QScrollBar::add-line:vertical {
            height: 0px;
            background: none;
            border: none;
        }
        QScrollBar::sub-line:vertical {
            height: 0px;
            background: none;
            border: none;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: #2b2b2b;
        }
        QScrollBar:horizontal {
            background-color: #2b2b2b;
            height: 12px;
            border: none;
            margin: 0px;
        }
        QScrollBar::handle:horizontal {
            background-color: #555555;
            border-radius: 6px;
            min-width: 20px;
            margin: 2px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #6a6a6a;
        }
        QScrollBar::add-line:horizontal {
            width: 0px;
            background: none;
            border: none;
        }
        QScrollBar::sub-line:horizontal {
            width: 0px;
            background: none;
            border: none;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: #2b2b2b;
        }
        
        /* 对话框样式 */
        QDialog {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }
        
        /* 分组框样式 */
        QGroupBox {
            background-color: transparent;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 5px;
            margin-top: 10px;
            font-weight: bold;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        
        /* 普通框架样式 */
        QFrame {
            background-color: #2b2b2b;
            border: none;
        }
        
        /* 消息框样式 */
        QMessageBox {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }
        QMessageBox QPushButton {
            min-width: 80px;
        }
        """)
        
        window = MainWindow()
        window.show()
        
        exit_code = app.exec_()
        
        # 清理资源
        from query_tool.utils.session_manager import session_manager
        session_manager.close_all()
        logger.info("应用程序正常退出")
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"应用程序崩溃: {e}", exc_info=True)
        # 显示错误对话框
        try:
            from PyQt5.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("程序错误")
            msg.setText("程序遇到严重错误，即将退出")
            msg.setInformativeText(f"错误信息：{str(e)}")
            msg.setDetailedText(f"详细信息请查看日志文件")
            msg.exec_()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
