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
    QPushButton, QStatusBar, QStackedWidget, QDesktopWidget,
    QSystemTrayIcon, QMenu, QAction
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
from query_tool.utils.style_manager import StyleManager
from query_tool.utils.theme_manager import theme_manager
from query_tool.widgets import SettingsDialog

# 禁用SSL警告
requests.packages.urllib3.disable_warnings()


def set_title_bar_theme(window, dark: bool = True):
    """设置标题栏深/浅色模式（Windows 10/11）"""
    try:
        hwnd = window.winId().__int__()
        value = ctypes.c_int(1 if dark else 0)
        for attr_id in (20, 19):  # 先试 Win11 方式，再试 Win10
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr_id, ctypes.byref(value), ctypes.sizeof(value)
                )
                return
            except Exception:
                continue
    except Exception as e:
        print(f"设置标题栏主题失败: {e}")


# 向后兼容别名
def set_dark_title_bar(window):
    set_title_bar_theme(window, dark=True)


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("查询工具")
        self.setMinimumSize(600, 450)
        self.setWindowIcon(QIcon(":/icons/app/logo.png"))
        self._apply_initial_window_size()
        
        # 页面实例
        self.pages = []
        self.page_buttons = []
        
        # 更新管理器
        self.update_manager = None
        self.pending_update_file = None  # 待安装的更新文件
        self._restart_after_update = False  # 是否在更新后重启程序
        self._force_close = False  # 是否允许真正退出
        self._tray_icon = None
        self._tray_message_shown = False
        
        self.init_ui()
        self._setup_system_tray()
        self.load_config()
        self.center_on_screen()
        
        # 设置标题栏主题（需要在窗口显示后调用）
        QTimer.singleShot(0, lambda: set_title_bar_theme(self, theme_manager.is_dark))
        
        # 监听主题切换
        theme_manager.theme_changed.connect(self._on_theme_changed)
        # 启动时检查更新
        QTimer.singleShot(2000, self.check_update_on_startup)

        # 启动时同步用户版本信息到飞书
        QTimer.singleShot(3000, self._sync_user_data)

        # 定时检查更新（每 6 小时）
        self._periodic_update_timer = QTimer(self)
        self._periodic_update_timer.timeout.connect(self._periodic_update_check)
        self._periodic_update_timer.start(6 * 60 * 60 * 1000)  # 6 小时

    def _get_available_geometry(self):
        """获取当前可用屏幕区域，避开任务栏。"""
        app = QApplication.instance()
        screen = app.primaryScreen() if app else None
        if screen is not None:
            return screen.availableGeometry()
        return QDesktopWidget().availableGeometry()

    def _apply_initial_window_size(self):
        """根据屏幕分辨率自适应设置窗口初始大小。"""
        available = self._get_available_geometry()
        target_width = max(self.minimumWidth(), min(1100, int(available.width() * 0.76)))
        target_height = max(self.minimumHeight(), min(720, int(available.height() * 0.78)))
        self.resize(min(target_width, available.width()), min(target_height, available.height()))
    
    def init_ui(self):
        """初始化UI"""
        # 创建自定义菜单栏
        menu_widget = QWidget()
        self._menu_widget = menu_widget  # 保存引用供主题刷新使用
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
        
        # 主题切换按钮
        self.theme_btn = QPushButton()
        self.theme_btn.setFixedSize(32, 28)
        self.theme_btn.setToolTip("切换浅色/深色模式")
        self._update_theme_btn_icon()
        StyleManager.apply_to_widget(self.theme_btn, "SETTINGS_BUTTON")
        self.theme_btn.clicked.connect(self._toggle_theme)
        
        menu_layout.addStretch()
        menu_layout.addWidget(self.theme_btn)
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
        self.status_label.setStyleSheet(f"color: {theme_manager.token('text_primary')}; padding-left: 5px;")
        self.status_bar.addWidget(self.status_label, 1)
        
        # 下载进度标签 - 右侧
        self.download_progress_label = QLabel("")
        self.download_progress_label.setStyleSheet(f"color: {theme_manager.token('status_info')}; padding-right: 10px;")
        self.download_progress_label.setVisible(False)  # 默认隐藏
        self.status_bar.addPermanentWidget(self.download_progress_label)
        
        # 呼吸闪烁标签（用于静默更新） - 右侧
        from query_tool.widgets.custom_widgets import BreathingLabel
        self.breathing_label = BreathingLabel()
        self.breathing_label.setVisible(False)  # 默认隐藏
        self.status_bar.addPermanentWidget(self.breathing_label)
        
        self.status_bar.showMessage("就绪")
        self.show_info("就绪")
        
        # 加载上次选择的页面
        app_config = config_manager.load_app_config()
        page_index = app_config.last_page_index
        if 0 <= page_index < len(self.pages):
            self.switch_page(page_index)
        else:
            self.switch_page(0)

    def _setup_system_tray(self):
        """初始化系统托盘。"""
        from query_tool.utils.logger import logger

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用，关闭按钮将退化为最小化到任务栏")
            return

        tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        tray_icon.setToolTip(self.windowTitle())

        tray_menu = QMenu(self)
        show_action = QAction("打开主窗口", self)
        show_action.triggered.connect(self.restore_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        exit_action = QAction("退出程序", self)
        exit_action.triggered.connect(self.exit_application)
        tray_menu.addAction(exit_action)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.activated.connect(self._on_tray_icon_activated)
        tray_icon.show()

        self._tray_icon = tray_icon
        logger.info("系统托盘初始化完成")

    def _on_tray_icon_activated(self, reason):
        """托盘图标点击事件。"""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self):
        """从托盘恢复主窗口。"""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _bring_window_to_front(self):
        """确保主窗口可见并位于前台，便于弹出重要对话框。"""
        if not self.isVisible() or self.isMinimized():
            self.restore_from_tray()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def exit_application(self):
        """真正退出程序。"""
        app = QApplication.instance()
        self._force_close = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        if app is not None:
            app.setQuitOnLastWindowClosed(True)
        self.close()

    def _minimize_on_close(self):
        """点击关闭按钮时最小化而不是直接退出。"""
        from query_tool.utils.logger import logger

        self.save_config()

        if self._tray_icon is not None:
            self.hide()
            if not self._tray_message_shown:
                self._tray_icon.showMessage(
                    "查询工具",
                    "程序已最小化到系统托盘，双击托盘图标可恢复，右键可退出。",
                    QSystemTrayIcon.Information,
                    3000,
                )
                self._tray_message_shown = True
                app_config = config_manager.load_app_config()
                app_config.tray_minimize_tip_shown = True
                config_manager.save_app_config(app_config)
            logger.info("主窗口已隐藏到系统托盘")
            return

        self.showMinimized()
        logger.info("主窗口已最小化到任务栏")
    
    def switch_page(self, index):
        """切换页面"""
        from query_tool.utils.logger import logger
        
        if index < 0 or index >= len(self.pages):
            return
        
        page_configs = PageRegistry.get_all_pages()
        page_name = page_configs[index]['name'] if index < len(page_configs) else f"页面{index}"
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

    def get_page_by_name(self, page_name):
        """按页面名称获取页面实例和索引"""
        page_configs = PageRegistry.get_all_pages()
        for index, page_config in enumerate(page_configs):
            if page_config.get('name') == page_name and index < len(self.pages):
                return index, self.pages[index]
        return -1, None

    def open_debug_page_for_sn(self, sn):
        """切换到调试页并按 SN 发起连接"""
        index, page = self.get_page_by_name("调试")
        if page is None:
            return False

        self.switch_page(index)
        if hasattr(page, "connect_to_device_sn"):
            page.connect_to_device_sn(sn)
            return True
        return False
    
    def on_settings_clicked(self):
        """设置按钮点击"""
        dialog = SettingsDialog(self)
        dialog.exec_()

    def _update_theme_btn_icon(self):
        """更新主题切换按钮图标/文字"""
        if theme_manager.is_dark:
            self.theme_btn.setText("☀")  # 深色模式下显示太阳（切换到浅色）
            self.theme_btn.setToolTip("切换到浅色模式")
        else:
            self.theme_btn.setText("🌙")  # 浅色模式下显示月亮（切换到深色）
            self.theme_btn.setToolTip("切换到深色模式")

    def _toggle_theme(self):
        """切换主题"""
        theme_manager.toggle()
        # 保存到注册表
        app_config = config_manager.load_app_config()
        app_config.theme = 'dark' if theme_manager.is_dark else 'light'
        config_manager.save_app_config(app_config)

    def _on_theme_changed(self):
        """主题切换后刷新主窗口自身的样式"""
        from query_tool.utils import StyleManager
        from query_tool.utils.logger import logger
        try:
            # 刷新菜单栏
            if hasattr(self, '_menu_widget'):
                StyleManager.apply_to_widget(self._menu_widget, "MENU_BAR")
            for btn in self.page_buttons:
                StyleManager.apply_to_widget(btn, "MENU_BUTTON")
            StyleManager.apply_to_widget(self.settings_btn, "SETTINGS_BUTTON")
            StyleManager.apply_to_widget(self.theme_btn, "SETTINGS_BUTTON")
            self._update_theme_btn_icon()
            # 刷新状态栏标签颜色
            self.status_label.setStyleSheet(
                f"color: {theme_manager.token('text_primary')}; padding-left: 5px;"
            )
            self.download_progress_label.setStyleSheet(
                f"color: {theme_manager.token('status_info')}; padding-right: 10px;"
            )
            # 刷新标题栏
            set_title_bar_theme(self, theme_manager.is_dark)
        except Exception as e:
            logger.error(f"主窗口主题刷新失败: {e}")
        # 通知各页面刷新（每个 page 独立 try，互不影响）
        for page in self.pages:
            if hasattr(page, 'refresh_theme'):
                try:
                    page.refresh_theme()
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.error(f"页面 {getattr(page, 'page_name', page)} 主题刷新失败: {e}")
    
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

    def show_warning(self, message, duration=3000):
        """显示警告消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.WARNING, duration)
    
    def show_error(self, message, duration=5000):
        """显示错误消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.ERROR, duration)

    def show_progress(self, message):
        """显示进度消息"""
        from query_tool.utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.PROGRESS, None)
    
    def center_on_screen(self):
        """将窗口居中显示"""
        screen = self._get_available_geometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(screen.x() + max(0, x), screen.y() + max(0, y))
    
    def load_config(self):
        """加载配置"""
        for page in self.pages:
            if hasattr(page, 'load_config'):
                page.load_config()
        
        # 恢复上次的主题
        app_config = config_manager.load_app_config()
        self._tray_message_shown = app_config.tray_minimize_tip_shown
        if app_config.theme == 'light':
            theme_manager.set_light()
    def _sync_user_data(self):
        """同步用户版本信息到飞书"""
        from query_tool.utils.data_sync import sync_user_version
        sync_user_version()
    
    def save_config(self):
        """保存配置"""
        for page in self.pages:
            if hasattr(page, 'save_config'):
                page.save_config()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        from query_tool.utils.logger import logger

        if not self._force_close and not self.pending_update_file:
            self._minimize_on_close()
            event.ignore()
            return
        
        # 停止定时器
        if hasattr(self, '_periodic_update_timer'):
            self._periodic_update_timer.stop()
        
        # 停止呼吸动画
        if hasattr(self, 'breathing_label'):
            self.breathing_label.stop()
        
        # 检查是否正在下载
        if self.update_manager and hasattr(self.update_manager, 'downloader'):
            if self.update_manager.downloader.download_thread and \
               self.update_manager.downloader.download_thread.isRunning():
                logger.info("检测到正在下载更新，取消下载...")
                # 设置取消标志，但不等待线程完成
                self.update_manager.downloader.download_thread.cancel()
                # 隐藏下载进度标签
                self.download_progress_label.setVisible(False)
                self.breathing_label.setVisible(False)
        
        # 保存配置
        self.save_config()
        
        # 清理资源
        for page in self.pages:
            if hasattr(page, 'cleanup'):
                page.cleanup()
        
        # 如果有待安装的更新，在关闭时安装
        if self.pending_update_file:
            try:
                from query_tool.utils.update_downloader import UpdateInstaller
                import os
                import subprocess
                
                logger.info("检测到待安装的更新，准备安装...")
                
                # 根据标志决定是否在安装后重启程序
                restart = self._restart_after_update
                logger.info(f"安装后是否重启程序: {restart}")
                
                if not UpdateInstaller.can_apply_update():
                    logger.warning("当前运行方式不支持自动更新安装，跳过本次自动安装")
                    event.accept()
                    return
                
                new_exe_path = self.pending_update_file
                current_exe_path = UpdateInstaller.get_current_executable_path()
                script_path = UpdateInstaller.create_update_script(
                    new_exe_path,
                    current_exe_path,
                    restart,
                )
                
                logger.info(f"更新脚本已创建: {script_path}")
                logger.info("启动更新脚本...")
                
                # 启动脚本（不等待）
                subprocess.Popen(
                    ['cmd', '/c', script_path],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                logger.info("更新脚本已启动，程序即将退出")
                
            except Exception as e:
                logger.error(f"安装更新失败: {e}")
        
        event.accept()
    
    def _periodic_update_check(self):
        """定时检查更新（运行期间每 3 小时触发一次，强制刷新，不走缓存）"""
        try:
            from query_tool.utils.logger import logger
            
            if not hasattr(self, 'update_manager') or self.update_manager is None:
                return
            
            if not self.update_manager.should_auto_check():
                return
            
            logger.info("定时检查更新（强制刷新）...")
            
            def callback(has_update, version_info, message):
                if has_update:
                    logger.info(f"定时检查发现新版本: {version_info}")
                    self.update_manager.latest_version_info = version_info
                    self.update_manager.update_available.emit(version_info)
                else:
                    logger.info(f"定时检查更新: {message}")
            
            self.update_manager.checker.check_update_async_force_refresh(callback)
            
        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"定时检查更新失败: {e}")

    def check_update_on_startup(self):
        """启动时检查更新"""
        try:
            from query_tool.utils.update_manager import UpdateManager
            from query_tool.version import get_short_version
            from query_tool.utils.logger import logger
            from pathlib import Path
            import hashlib
            
            # 获取当前版本号（去掉 V 前缀）
            current_version = get_short_version().replace('V', '')
            
            # 创建更新管理器
            self.update_manager = UpdateManager(current_version, self)
            
            # 检查下载目录中是否有已下载的文件（用于恢复中断的更新）
            download_dir = Path.home() / '.TPQueryTool' / 'downloads'
            if download_dir.exists():
                exe_files = list(download_dir.glob('TPQueryTool_*.exe'))
                if exe_files:
                    # 找到最新的文件
                    latest_file = max(exe_files, key=lambda x: x.stat().st_mtime)
                    logger.info(f"发现已下载的文件: {latest_file}")
                    
                    # 获取 version.json 中的哈希值进行校验
                    cached_info = self.update_manager.checker._load_cache()
                    if cached_info and cached_info.file_hash:
                        logger.info(f"开始验证文件哈希...")
                        
                        # 计算文件哈希
                        try:
                            hash_obj = hashlib.sha256()
                            with open(latest_file, 'rb') as f:
                                while True:
                                    chunk = f.read(8192)
                                    if not chunk:
                                        break
                                    hash_obj.update(chunk)
                            
                            actual_hash = hash_obj.hexdigest()
                            expected_hash = cached_info.file_hash
                            
                            logger.info(f"期望哈希: {expected_hash}")
                            logger.info(f"实际哈希: {actual_hash}")
                            
                            if actual_hash.lower() != expected_hash.lower():
                                logger.error("文件哈希校验失败，文件可能已损坏或不匹配")
                                logger.info("删除损坏的文件，将重新检查更新")
                                try:
                                    latest_file.unlink()
                                except Exception as e:
                                    logger.error(f"删除文件失败: {e}")
                                # 继续正常的更新检查流程
                            else:
                                logger.info("✓ 文件哈希校验通过")
                                
                                # 检查更新策略
                                strategy = self.update_manager.get_update_strategy()
                                
                                if strategy == 'silent':
                                    from query_tool.utils.update_downloader import UpdateInstaller
                                    if UpdateInstaller.can_apply_update():
                                        # 静默模式：直接安装
                                        logger.info("静默模式，直接安装已下载的文件")
                                        self.pending_update_file = str(latest_file)
                                        # 设置标志为 True，表示安装后需要重新打开程序
                                        self._restart_after_update = True
                                        # 立即关闭程序并安装
                                        self.close()
                                        return
                                    logger.warning("当前运行方式不支持自动安装已下载更新，跳过启动时自动应用")
                                elif strategy == 'prompt':
                                    # 提示模式：弹窗询问用户是否立即重启
                                    logger.info("提示模式，弹窗询问用户是否立即重启")
                                    self._show_update_ready_dialog(str(latest_file))
                                    return
                        except Exception as e:
                            logger.error(f"计算文件哈希失败: {e}")
                            logger.info("无法验证文件，将重新检查更新")
                    else:
                        logger.warning("未找到缓存的版本信息或哈希值，无法验证文件")
                        logger.info("将重新检查更新")
            
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
            # 静默更新：后台下载，不显示任何提示
            logger.info("静默更新模式，开始后台下载...")
            self.start_download_update(version_info)
    
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
        
        strategy = self.update_manager.get_update_strategy()
        logger.info(f"更新策略: {strategy}")
        
        if strategy == 'silent':
            # 静默模式：只显示绿色呼吸闪烁提示
            logger.info("静默更新模式，显示呼吸闪烁提示")
            logger.info(f"breathing_label 存在: {hasattr(self, 'breathing_label')}")
            logger.info(f"breathing_label 对象: {self.breathing_label}")
            self.breathing_label.setVisible(True)
            self.download_progress_label.setVisible(False)
            logger.info("已设置 breathing_label 可见")
        else:
            # 提示模式：显示下载进度
            logger.info("提示更新模式，显示下载进度")
            self.download_progress_label.setText(f"正在下载更新 V{version_info.version}...")
            self.download_progress_label.setVisible(True)
            self.breathing_label.setVisible(False)
        
        # 开始下载
        self.update_manager.download_update(version_info)
    
    def on_download_progress(self, downloaded, total):
        """下载进度更新"""
        strategy = self.update_manager.get_update_strategy()
        
        if strategy == 'silent':
            # 静默模式：不显示进度，只显示呼吸闪烁
            pass
        else:
            # 提示模式：显示下载进度
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
            
            if strategy in ('manual', 'prompt'):
                # 手动/提示模式：停止呼吸闪烁，隐藏呼吸标签
                self.breathing_label.stop()
                self.breathing_label.setVisible(False)
                
                # 显示下载完成消息，然后弹出重启对话框
                self.show_success("更新下载完成", 2000)
                
                from query_tool.utils.update_downloader import UpdateInstaller
                if not UpdateInstaller.can_apply_update():
                    from PyQt5.QtWidgets import QMessageBox
                    QMessageBox.information(
                        self,
                        "更新已下载",
                        "更新已下载完成。\n\n"
                        "当前运行方式不支持自动覆盖安装。\n"
                        "已保留安装包，可手动替换或使用发布版程序完成更新。"
                    )
                    return
                
                # 延迟显示重启对话框，让用户看到成功消息
                QTimer.singleShot(500, self._show_update_complete_dialog_with_focus)
            
            elif strategy == 'silent':
                # 静默模式：下载完成后主动提醒用户重启升级
                self.breathing_label.stop()
                self.breathing_label.set_color("#4a9eff", breathing=False)
                self.pending_update_file = result
                logger.info("静默更新已下载完成，准备提示用户重启安装")
                self.show_success("更新下载完成，请重启程序完成升级", 4000)

                from query_tool.utils.update_downloader import UpdateInstaller
                if not UpdateInstaller.can_apply_update():
                    from PyQt5.QtWidgets import QMessageBox
                    self._bring_window_to_front()
                    QMessageBox.information(
                        self,
                        "更新已下载",
                        "更新已下载完成。\n\n"
                        "当前运行方式不支持自动覆盖安装。\n"
                        "已保留安装包，可手动替换或使用发布版程序完成更新。"
                    )
                    return

                QTimer.singleShot(300, self._show_update_complete_dialog_with_focus)
        
        else:
            logger.error(f"下载失败: {result}")
            
            # 隐藏下载进度标签和呼吸闪烁
            self.download_progress_label.setVisible(False)
            self.breathing_label.stop()
            self.breathing_label.setVisible(False)
            
            strategy = self.update_manager.get_update_strategy()
            
            # 只在非 silent 模式下显示错误提示
            if strategy != 'silent':
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
        
        dialog.exec_()

    def _show_update_complete_dialog_with_focus(self):
        """拉起主窗口后显示更新完成对话框。"""
        self._bring_window_to_front()
        self.show_update_complete_dialog()
    
    def _on_restart_later(self):
        """用户选择稍后重启"""
        from query_tool.utils.logger import logger
        
        logger.info("用户选择稍后重启")
        
        # 保存下载的文件路径，等待程序关闭时安装
        if self.update_manager and self.update_manager.downloaded_file_path:
            self.pending_update_file = self.update_manager.downloaded_file_path
            logger.info(f"已保存待安装文件: {self.pending_update_file}")
    
    def _show_update_ready_dialog(self, file_path):
        """显示更新已准备好的对话框（启动时检测到已下载的文件）"""
        from PyQt5.QtWidgets import QMessageBox
        from query_tool.utils.logger import logger
        from query_tool.utils.update_downloader import UpdateInstaller
        
        logger.info(f"显示更新已准备好对话框: {file_path}")
        
        # 设置更新管理器的下载文件路径
        if self.update_manager:
            self.update_manager.downloaded_file_path = file_path

        if not UpdateInstaller.can_apply_update():
            QMessageBox.information(
                self,
                "更新已下载",
                "检测到更新安装包已下载完成。\n\n"
                "当前运行方式不支持自动覆盖安装。\n"
                "已保留安装包，可手动替换或使用发布版程序完成更新。"
            )
            return
        
        # 弹窗询问用户
        reply = QMessageBox.question(
            self,
            "更新已准备好",
            "检测到更新已下载完成，是否立即重启并安装？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            logger.info("用户选择立即重启")
            self.apply_update_and_restart()
        else:
            logger.info("用户选择稍后重启")
            self._on_restart_later()
    
    def apply_update_and_restart(self):
        """应用更新并重启"""
        from query_tool.utils.logger import logger
        from PyQt5.QtWidgets import QMessageBox
        from query_tool.utils.update_downloader import UpdateInstaller
        
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

            if not UpdateInstaller.can_apply_update():
                QMessageBox.information(
                    self,
                    "更新已下载",
                    "当前运行方式不支持自动覆盖安装。\n"
                    "已保留安装包，可手动替换或使用发布版程序完成更新。"
                )
                return
            
            # 设置标志，表示更新后需要重启程序
            self._restart_after_update = True
            self.pending_update_file = self.update_manager.downloaded_file_path
            
            # 关闭程序，触发 closeEvent 中的安装逻辑
            logger.info("关闭程序以执行更新...")
            self.close()
            
        except Exception as e:
            logger.error(f"应用更新失败: {e}", exc_info=True)
            QMessageBox.critical(
                self, 
                "更新失败", 
                f"应用更新时发生错误：\n\n{str(e)}\n\n请查看日志文件获取详细信息。"
            )
            self.show_error(f"应用更新失败: {e}", 5000)


def _get_windows_theme() -> str:
    """读取 Windows 系统深/浅色偏好，返回 'dark' 或 'light'"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return 'light' if value == 1 else 'dark'
    except Exception:
        return 'dark'  # 读取失败默认深色


def _get_startup_theme() -> str:
    """
    决定启动时使用的主题：
    - 用户已手动设置过（注册表有 theme 键）→ 使用用户偏好
    - 首次启动（无 theme 键）→ 跟随 Windows 系统主题
    """
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\TPQueryTool",
            0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, "theme")
        winreg.CloseKey(key)
        return value  # 用户已设置过，直接用
    except (FileNotFoundError, OSError):
        # 首次启动，跟随系统
        return _get_windows_theme()


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
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app = QApplication(sys.argv)
        
        # 在创建任何控件之前，先从注册表读取并应用保存的主题
        # 这样 init_ui 里所有控件直接用正确主题的颜色创建，无需事后刷新
        from query_tool.utils.theme_manager import LIGHT_THEME
        _saved_theme = _get_startup_theme()
        if _saved_theme == 'light':
            # 直接修改内部状态，不触发信号（此时还没有任何控件需要刷新）
            theme_manager._is_dark = False
            theme_manager._tokens = LIGHT_THEME.copy()
        
        # 设置全局主题样式
        app.setStyleSheet(StyleManager.build_global_stylesheet())
        
        # 主题切换时刷新全局样式
        def _on_global_theme_changed():
            app.setStyleSheet(StyleManager.build_global_stylesheet())
        
        theme_manager.theme_changed.connect(_on_global_theme_changed)
        
        window = MainWindow()
        app.setQuitOnLastWindowClosed(window._tray_icon is None)
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
