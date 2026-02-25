"""
更新对话框
"""
import ctypes
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QProgressBar, QTextEdit, QWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from query_tool.utils.update_checker import VersionInfo


def set_dark_title_bar(window):
    """设置深色标题栏（Windows 10/11）"""
    try:
        hwnd = window.winId().__int__()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        try:
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                ctypes.byref(value),
                ctypes.sizeof(value)
            )
        except:
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


class UpdatePromptDialog(QDialog):
    """更新提示对话框"""
    
    # 信号
    update_now = pyqtSignal()
    remind_later = pyqtSignal()
    skip_version = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, current_version: str, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        self.current_version = current_version
        
        self.setWindowTitle("发现新版本")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._init_ui()
        self._apply_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"🎉 发现新版本 V{self.version_info.version}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 版本信息
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        info_layout.addWidget(QLabel(f"当前版本：V{self.current_version}"))
        info_layout.addWidget(QLabel(f"最新版本：V{self.version_info.version}"))
        info_layout.addWidget(QLabel(f"编译日期：{self._format_date(self.version_info.build_date)}"))
        info_layout.addWidget(QLabel(f"文件大小：{self.version_info.file_size_mb} MB"))
        
        layout.addWidget(info_widget)
        
        # 更新内容
        changelog_label = QLabel("更新内容：")
        changelog_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(changelog_label)
        
        changelog_text = QTextEdit()
        changelog_text.setReadOnly(True)
        changelog_text.setMaximumHeight(150)
        
        # 填充更新日志
        changelog_content = "\n".join([f"• {item}" for item in self.version_info.changelog[:10]])
        changelog_text.setPlainText(changelog_content)
        
        layout.addWidget(changelog_text)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        update_btn = QPushButton("立即更新")
        update_btn.setMinimumWidth(100)
        update_btn.clicked.connect(self._on_update_now)
        button_layout.addWidget(update_btn)
        
        later_btn = QPushButton("稍后提醒")
        later_btn.setMinimumWidth(100)
        later_btn.clicked.connect(self._on_remind_later)
        button_layout.addWidget(later_btn)
        
        skip_btn = QPushButton("跳过此版本")
        skip_btn.setMinimumWidth(100)
        skip_btn.clicked.connect(self._on_skip_version)
        button_layout.addWidget(skip_btn)
        
        layout.addLayout(button_layout)
    
    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        try:
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return date_str
        except:
            return date_str
    
    def _apply_style(self):
        """应用样式"""
        set_dark_title_bar(self)
    
    def _on_update_now(self):
        """立即更新"""
        self.update_now.emit()
        self.accept()
    
    def _on_remind_later(self):
        """稍后提醒"""
        self.remind_later.emit()
        self.reject()
    
    def _on_skip_version(self):
        """跳过此版本"""
        self.skip_version.emit()
        self.reject()


class UpdateDownloadDialog(QDialog):
    """更新下载对话框"""
    
    # 信号
    cancel_download = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        
        self.setWindowTitle("下载更新")
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self._init_ui()
        self._apply_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"正在下载 V{self.version_info.version}")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("准备下载...")
        layout.addWidget(self.status_label)
        
        # 取消按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def update_progress(self, downloaded: int, total: int):
        """
        更新进度
        
        Args:
            downloaded: 已下载字节数
            total: 总字节数
        """
        if total > 0:
            progress = int((downloaded / total) * 100)
            self.progress_bar.setValue(progress)
            
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            
            self.status_label.setText(
                f"已下载 {downloaded_mb:.2f} MB / {total_mb:.2f} MB"
            )
    
    def _apply_style(self):
        """应用样式"""
        set_dark_title_bar(self)
    
    def _on_cancel(self):
        """取消下载"""
        self.cancel_download.emit()
        self.reject()


class UpdateCompleteDialog(QDialog):
    """更新完成对话框"""
    
    # 信号
    restart_now = pyqtSignal()
    restart_later = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        
        self.setWindowTitle("更新完成")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        
        self._init_ui()
        self._apply_style()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题
        title_label = QLabel(f"✓ 更新下载完成")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 提示信息
        info_label = QLabel(
            f"V{self.version_info.version} 已下载完成\n\n"
            "点击「立即重启」应用更新\n"
            "或点击「稍后重启」在下次启动时更新"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        restart_btn = QPushButton("立即重启")
        restart_btn.setMinimumWidth(100)
        restart_btn.clicked.connect(self._on_restart_now)
        button_layout.addWidget(restart_btn)
        
        later_btn = QPushButton("稍后重启")
        later_btn.setMinimumWidth(100)
        later_btn.clicked.connect(self._on_restart_later)
        button_layout.addWidget(later_btn)
        
        layout.addLayout(button_layout)
    
    def _apply_style(self):
        """应用样式"""
        set_dark_title_bar(self)
    
    def _on_restart_now(self):
        """立即重启"""
        self.restart_now.emit()
        self.accept()
    
    def _on_restart_later(self):
        """稍后重启"""
        self.restart_later.emit()
        self.reject()
