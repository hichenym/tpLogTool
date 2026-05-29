"""
更新对话框
"""
import ctypes
import resources.icon_res as icon_res
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QWidget, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QMovie

from query_tool.utils.update_checker import VersionInfo
from query_tool.utils.theme_manager import t


def set_dark_title_bar(window):
    """根据当前主题设置标题栏"""
    from query_tool.utils.theme_manager import theme_manager
    from query_tool.widgets.custom_widgets import set_title_bar_theme
    set_title_bar_theme(window, dark=theme_manager.is_dark)


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
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
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
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
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
    
    def _on_cancel(self):
        """取消下载"""
        self.cancel_download.emit()
        self.reject()


class UpdateCompleteDialog(QDialog):
    """更新完成对话框"""
    
    # 信号
    restart_now = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        self._change_lines = [str(item).strip() for item in self.version_info.changelog if str(item).strip()]
        self._show_change_content = bool(self.version_info.show_change and self._change_lines)
        self._icon_movie = None
        
        self.setWindowTitle("功能变更")
        self.setWindowIcon(QIcon(":/icons/app/logo.png"))
        fixed_size = QSize(500, 270 if self._show_change_content else 205)
        self.setFixedSize(fixed_size)
        self.setMinimumSize(fixed_size)
        self.setMaximumSize(fixed_size)
        self.setSizeGripEnabled(False)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint)
        self.setWindowModality(Qt.ApplicationModal)
        
        self._init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        panel_frame = QFrame()
        panel_frame.setObjectName("panelFrame")
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(20, 18, 20, 16)
        panel_layout.setSpacing(14)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(14)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("heroIcon")
        self.icon_label.setFixedSize(60, 60)
        self.icon_label.setAlignment(Qt.AlignCenter)
        hero_row.addWidget(self.icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        title_label = QLabel("检测到功能变更")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setObjectName("titleLabel")
        text_layout.addWidget(title_label)

        subtitle_label = QLabel(self._build_subtitle_text())
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("subtitleLabel")
        text_layout.addWidget(subtitle_label)
        hero_row.addLayout(text_layout, 1)
        panel_layout.addLayout(hero_row)

        if self._show_change_content:
            divider = QFrame()
            divider.setObjectName("divider")
            divider.setFixedHeight(1)
            panel_layout.addWidget(divider)

            change_text = QTextEdit()
            change_text.setReadOnly(True)
            change_text.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            change_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            change_text.setMinimumHeight(74)
            change_text.setMaximumHeight(88)
            change_text.setObjectName("changeText")
            change_text.setPlainText("\n".join([f"• {item}" for item in self._change_lines[:10]]))
            panel_layout.addWidget(change_text)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        restart_btn = QPushButton("立即重启")
        restart_btn.setFixedSize(116, 36)
        restart_btn.setCursor(Qt.PointingHandCursor)
        restart_btn.setObjectName("primaryButton")
        restart_btn.clicked.connect(self._on_restart_now)
        button_layout.addWidget(restart_btn)

        layout.addWidget(panel_frame)
        layout.addLayout(button_layout)
        self._setup_movie()
        self._apply_styles()

    def _build_subtitle_text(self) -> str:
        if self._show_change_content:
            return "检测到下列功能变更，重启程序以应用"
        return "检测到功能变更，重启程序以应用"

    def _setup_movie(self):
        movie = QMovie(":/icons/common/running.gif")
        if not movie.isValid():
            self.icon_label.setText("i")
            self.icon_label.setAlignment(Qt.AlignCenter)
            self.icon_label.setObjectName("fallbackIcon")
            return
        movie.setScaledSize(QSize(60, 60))
        self._icon_movie = movie
        self.icon_label.setMovie(movie)
        movie.start()

    def _apply_styles(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {t('bg_dark')};
            }}
            QFrame {{
                border: none;
            }}
            QFrame#panelFrame {{
                background-color: {t('bg_mid')};
                border: 1px solid {t('border')};
                border-radius: 14px;
            }}
            QFrame#divider {{
                background-color: {t('border')};
            }}
            QLabel {{
                color: {t('text_primary')};
                background: transparent;
            }}
            QLabel#titleLabel {{
                color: {t('text_primary')};
            }}
            QLabel#subtitleLabel {{
                color: {t('text_secondary')};
                font-size: 12px;
            }}
            QLabel#heroIcon, QLabel#fallbackIcon {{
                background: transparent;
            }}
            QTextEdit#changeText {{
                background-color: transparent;
                color: {t('text_primary')};
                border: none;
                padding: 0px;
                font-size: 12px;
            }}
            QPushButton {{
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
            }}
            QPushButton#primaryButton {{
                background-color: {t('accent')};
                color: #ffffff;
                border: 1px solid {t('accent')};
            }}
            QPushButton#primaryButton:hover {{
                background-color: {t('accent_dim')};
                border: 1px solid {t('accent_dim')};
            }}
            QPushButton#primaryButton:pressed {{
                background-color: {t('accent_dim')};
            }}
            """
        )
    
    def _on_restart_now(self):
        """立即重启"""
        self.restart_now.emit()
        self.accept()
