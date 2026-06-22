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
from PyQt5.QtGui import QIcon, QMovie
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
from query_tool.utils.task_center import (
    TASK_STATUS_PAUSED,
    count_all_tasks,
    count_running_tasks,
    list_tasks,
    pause_all_actionable_tasks,
)
from query_tool.utils.theme_manager import theme_manager
from query_tool.utils.single_instance import SingleInstanceController
from query_tool.widgets import SettingsDialog, TaskCenterDialog

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
        
        self._force_close = False  # 是否允许真正退出
        self._tray_icon = None
        self._tray_message_shown = False
        self._task_button_movie = None
        self._task_button_movie_path = None

        self.init_ui()
        self._setup_system_tray()
        self.load_config()
        self.center_on_screen()
        
        # 设置标题栏主题（需要在窗口显示后调用）
        QTimer.singleShot(0, lambda: set_title_bar_theme(self, theme_manager.is_dark))
        
        # 监听主题切换
        theme_manager.theme_changed.connect(self._on_theme_changed)

        self._task_indicator_timer = QTimer(self)
        self._task_indicator_timer.timeout.connect(self.refresh_running_task_indicator)
        self._task_indicator_timer.start(2000)
        QTimer.singleShot(0, self.refresh_running_task_indicator)

    def _get_available_geometry(self):
        """获取当前可用屏幕区域，避开任务栏。"""
        desktop = QDesktopWidget()
        if self.isVisible():
            return desktop.availableGeometry(self)
        parent = self.parentWidget()
        if parent is not None:
            return desktop.availableGeometry(parent)
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

        self.task_center_btn = QPushButton("任务运行中")
        self.task_center_btn.setIconSize(QSize(16, 16))
        self.task_center_btn.setFixedHeight(28)
        self.task_center_btn.setVisible(False)
        StyleManager.apply_to_widget(self.task_center_btn, "SETTINGS_BUTTON")
        self.task_center_btn.clicked.connect(self.open_task_center)
        self._set_task_button_static_icon(":/icons/common/run.png")
        
        menu_layout.addStretch()
        menu_layout.addWidget(self.task_center_btn)
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

    def handle_activation_request(self):
        """处理其他启动请求，恢复当前主窗口。"""
        if self.isHidden() or self.isMinimized():
            self.restore_from_tray()
            return
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

    def _set_task_button_static_icon(self, icon_path: str):
        if self._task_button_movie is not None:
            self._task_button_movie.stop()
            try:
                self._task_button_movie.frameChanged.disconnect(self._on_task_button_movie_frame_changed)
            except Exception:
                pass
            self._task_button_movie = None
            self._task_button_movie_path = None
        self.task_center_btn.setIcon(QIcon(icon_path))

    def _start_task_button_movie(self, resource_path: str):
        if self._task_button_movie_path == resource_path and self._task_button_movie is not None:
            if self._task_button_movie.state() != QMovie.Running:
                self._task_button_movie.start()
            return
        if self._task_button_movie is not None:
            self._task_button_movie.stop()
            try:
                self._task_button_movie.frameChanged.disconnect(self._on_task_button_movie_frame_changed)
            except Exception:
                pass

        movie = QMovie(resource_path)
        if not movie.isValid():
            self._set_task_button_static_icon(":/icons/common/run.png")
            return
        movie.setCacheMode(QMovie.CacheAll)
        movie.frameChanged.connect(self._on_task_button_movie_frame_changed)
        self._task_button_movie = movie
        self._task_button_movie_path = resource_path
        movie.start()

    def _on_task_button_movie_frame_changed(self, _frame_number: int):
        if self._task_button_movie is None:
            return
        pixmap = self._task_button_movie.currentPixmap()
        if pixmap.isNull():
            return
        self.task_center_btn.setIcon(QIcon(pixmap))

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
            StyleManager.apply_to_widget(self.task_center_btn, "SETTINGS_BUTTON")
            self._update_theme_btn_icon()
            # 刷新状态栏标签颜色
            self.status_label.setStyleSheet(
                f"color: {theme_manager.token('text_primary')}; padding-left: 5px;"
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

    def refresh_running_task_indicator(self):
        """Refresh the running-task indicator in the title bar."""
        try:
            running_count = count_running_tasks()
            total_count = count_all_tasks()
            paused_count = len([task for task in list_tasks() if task.get("status") == TASK_STATUS_PAUSED])
            finished_count = len([task for task in list_tasks() if task.get("status") in ("completed", "failed", "canceled")])
        except Exception:
            running_count = 0
            total_count = 0
            paused_count = 0
            finished_count = 0

        self.task_center_btn.setVisible(total_count > 0)
        if running_count > 0:
            self._start_task_button_movie(":/icons/common/loadding.gif")
            self.task_center_btn.setText(f"任务运行中({running_count})")
            self.task_center_btn.setToolTip(f"当前有 {running_count} 个后台任务运行中")
            return
        if paused_count > 0:
            self._set_task_button_static_icon(":/icons/common/run.png")
            self.task_center_btn.setText(f"任务已暂停({paused_count})")
            self.task_center_btn.setToolTip(f"当前有 {paused_count} 个后台任务已暂停")
            return
        if finished_count > 0:
            self._start_task_button_movie(":/icons/common/finish2.gif")
            self.task_center_btn.setText("任务已完成")
            self.task_center_btn.setToolTip(f"当前共有 {finished_count} 个后台任务已结束")
            return
        self._set_task_button_static_icon(":/icons/common/run.png")

    def open_task_center(self):
        """Open the background task center dialog."""
        dialog = TaskCenterDialog(self)
        dialog.exec_()
    
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
    
    def save_config(self):
        """保存配置"""
        for page in self.pages:
            if hasattr(page, 'save_config'):
                page.save_config()

    def _cleanup_pages_for_exit(self, fast: bool = False):
        """根据退出场景清理页面资源。"""
        from query_tool.utils.logger import logger

        cleanup_method = 'fast_cleanup' if fast else 'cleanup'
        for page in self.pages:
            try:
                method = getattr(page, cleanup_method, None)
                if callable(method):
                    method()
                elif not fast and hasattr(page, 'cleanup'):
                    page.cleanup()
            except Exception as e:
                logger.error(
                    f"页面资源清理失败 ({getattr(page, 'page_name', page)}, "
                    f"{'fast' if fast else 'normal'}): {e}"
                )

    def closeEvent(self, event):
        """窗口关闭事件"""
        if not self._force_close:
            self._minimize_on_close()
            event.ignore()
            return
        
        # 停止定时器
        if hasattr(self, '_task_indicator_timer'):
            self._task_indicator_timer.stop()

        # 保存配置
        self.save_config()

        self._cleanup_pages_for_exit()

        try:
            pause_all_actionable_tasks(stop_processes=True)
        except Exception:
            pass

        event.accept()


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


def _cleanup_legacy_update_artifacts() -> None:
    """清理遗留的注册表和缓存目录。"""
    from pathlib import Path
    import shutil
    import winreg

    from query_tool.utils.logger import logger

    update_root = r"Software\TPQueryTool\Update"
    reg_key = None
    try:
        reg_key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            update_root,
            0,
            winreg.KEY_READ | winreg.KEY_WRITE,
        )
        while True:
            try:
                child_name = winreg.EnumKey(reg_key, 0)
            except OSError:
                break
            winreg.DeleteKey(reg_key, child_name)
        winreg.CloseKey(reg_key)
        reg_key = None
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, update_root)
        logger.info("已清理历史更新注册表信息")
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning(f"清理历史更新注册表信息失败: {exc}")
    finally:
        if reg_key is not None:
            try:
                winreg.CloseKey(reg_key)
            except Exception:
                pass

    for cache_dir in (
        Path.home() / ".TPQueryTool" / "update",
        Path.home() / ".TPQueryTool" / "downloads",
    ):
        if not cache_dir.exists():
            continue
        try:
            shutil.rmtree(cache_dir)
            logger.info(f"已清理历史更新缓存目录: {cache_dir}")
        except Exception as exc:
            logger.warning(f"清理历史更新缓存目录失败 {cache_dir}: {exc}")


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
    _cleanup_legacy_update_artifacts()
    
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        app = QApplication(sys.argv)

        single_instance = SingleInstanceController.for_current_app(app)
        if SingleInstanceController.notify_existing_instance(single_instance.server_name):
            logger.info("检测到已有实例在运行，已通知其恢复主窗口")
            raise SystemExit(0)
        if not single_instance.start():
            logger.warning("单实例监听启动失败，将继续以普通模式运行")
        
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
        single_instance.activation_requested.connect(window.handle_activation_request)
        app._single_instance_controller = single_instance
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
