import sys
import ctypes
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStatusBar, QStackedWidget, QDesktopWidget
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QPalette, QColor
import requests

# 导入资源文件
import icon_res

# 导入版本信息
from version import get_version_string

# 导入页面
from pages import PageRegistry, DeviceStatusPage, PhoneQueryPage

# 导入工具和控件
from utils import config_manager
from widgets import ClickableLabel, SettingsDialog

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
        except:
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
        self.setWindowTitle("设备信息查询工具")
        self.setGeometry(100, 100, 600, 350)
        self.setMinimumSize(700, 450)
        self.setWindowIcon(QIcon(":/icon/logo.png"))
        
        # 页面实例
        self.pages = []
        self.page_buttons = []
        
        # 版本信息定时器
        self.version_timer = None
        
        self.init_ui()
        self.load_config()
        self.center_on_screen()
        
        # 设置深色标题栏（需要在窗口显示后调用）
        QTimer.singleShot(0, lambda: set_dark_title_bar(self))
    
    def init_ui(self):
        """初始化UI"""
        # 创建自定义菜单栏
        menu_widget = QWidget()
        menu_widget.setFixedHeight(28)
        menu_widget.setAutoFillBackground(True)  # 确保使用自定义背景
        from utils import StyleManager
        StyleManager.apply_to_widget(menu_widget, "MENU_BAR")
        menu_layout = QHBoxLayout(menu_widget)
        menu_layout.setContentsMargins(5, 0, 0, 0)
        menu_layout.setSpacing(0)
        
        # 从注册表获取所有页面并创建按钮
        for page_config in PageRegistry.get_all_pages():
            page_class = page_config['class']
            page_name = page_config['name']
            
            # 创建页面实例
            page = page_class(self)
            self.pages.append(page)
            
            # 创建菜单按钮
            btn = QPushButton(page_name)
            btn.setCheckable(True)
            StyleManager.apply_to_widget(btn, "MENU_BUTTON")
            btn.clicked.connect(lambda checked, idx=len(self.pages)-1: self.switch_page(idx))
            self.page_buttons.append(btn)
            menu_layout.addWidget(btn)
        
        # 设置按钮
        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(QIcon(":/icon/setting.png"))
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
        
        # 状态消息标签（支持富文本）
        from PyQt5.QtWidgets import QLabel
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setStyleSheet("color: #e0e0e0; padding-left: 5px;")
        self.status_bar.addWidget(self.status_label, 1)
        
        # 版本号标签
        from utils import StyleManager
        self.version_label = ClickableLabel("  ")
        self.version_label.setStyleSheet(StyleManager.VERSION_LABEL)
        self.version_label.clicked = self.on_version_clicked
        self.status_bar.addPermanentWidget(self.version_label)
        
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
        if index < 0 or index >= len(self.pages):
            return
        
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
        from utils.message_manager import MessageManager, MessageType
        
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
        from utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.INFO, duration)
    
    def show_success(self, message, duration=3000):
        """显示成功消息"""
        from utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.SUCCESS, duration)
    
    def show_error(self, message, duration=5000):
        """显示错误消息"""
        from utils.message_manager import MessageManager, MessageType
        msg_manager = MessageManager(self.status_label)
        msg_manager.show(message, MessageType.ERROR, duration)
    
    def on_version_clicked(self):
        """点击版本标签显示版本信息"""
        self.version_label.setText(get_version_string())
        
        if self.version_timer:
            self.version_timer.stop()
        
        self.version_timer = QTimer()
        self.version_timer.setSingleShot(True)
        self.version_timer.timeout.connect(self.hide_version)
        self.version_timer.start(1000)
    
    def hide_version(self):
        """隐藏版本信息"""
        self.version_label.setText("  ")
    
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
        # 保存配置
        self.save_config()
        
        # 清理资源
        for page in self.pages:
            if hasattr(page, 'cleanup'):
                page.cleanup()
        
        event.accept()


if __name__ == "__main__":
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
            selection-background-color: #0d7377;
        }
        
        /* 下拉框样式 */
        QComboBox {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
        }
        QComboBox:hover {
            border: 1px solid #0d7377;
        }
        QComboBox::drop-down {
            border: none;
            background-color: #3c3c3c;
        }
        QComboBox QAbstractItemView {
            background-color: #3c3c3c;
            color: #e0e0e0;
            selection-background-color: #0d7377;
            border: 1px solid #555555;
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
            border: 1px solid #0d7377;
        }
        QPushButton:pressed {
            background-color: #0d7377;
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
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #404040;
        }
        QCheckBox::indicator:hover {
            border: 1px solid #0d7377;
        }
        QCheckBox::indicator:checked {
            background-color: #0d7377;
            border: 1px solid #0d7377;
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
            background-color: #0d7377;
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
            background-color: #0d7377;
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
    sys.exit(app.exec_())
