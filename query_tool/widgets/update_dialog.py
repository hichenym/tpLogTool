"""
更新对话框
"""
import ctypes
import html
import resources.icon_res as icon_res
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit, QWidget, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QCursor, QFont, QIcon, QMovie

from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.utils.update_checker import VersionInfo
from query_tool.utils.theme_manager import t


def set_dark_title_bar(window):
    """根据当前主题设置标题栏"""
    from query_tool.utils.theme_manager import theme_manager
    from query_tool.widgets.custom_widgets import set_title_bar_theme
    set_title_bar_theme(window, dark=theme_manager.is_dark)


def _compute_fixed_dialog_size(parent, preferred_size: QSize, min_size: QSize, max_width_ratio: float, max_height_ratio: float) -> QSize:
    app = QApplication.instance()
    desktop = app.desktop() if app is not None else None
    if desktop is None:
        return QSize(preferred_size)

    if parent is not None:
        available = desktop.availableGeometry(parent.window())
    else:
        available = desktop.availableGeometry(desktop.screenNumber(QCursor.pos()))

    max_width = max(240, available.width() - 24)
    max_height = max(180, available.height() - 24)
    width = max(
        min_size.width(),
        min(preferred_size.width(), int(available.width() * max_width_ratio), max_width),
    )
    height = max(
        min_size.height(),
        min(preferred_size.height(), int(available.height() * max_height_ratio), max_height),
    )
    return QSize(width, height)


class UpdatePromptDialog(AdaptiveDialog):
    """更新提示对话框"""
    
    # 信号
    update_now = pyqtSignal()
    remind_later = pyqtSignal()
    skip_version = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, current_version: str, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        self.current_version = current_version
        self._change_lines = [str(item).strip() for item in self.version_info.changelog if str(item).strip()]
        self._show_change_content = bool(self._change_lines)
        self._icon_movie = None
        preferred_height = 360 if self._show_change_content else 300
        self._dialog_size = _compute_fixed_dialog_size(
            parent,
            QSize(560, preferred_height),
            QSize(460, 300),
            0.78,
            0.82,
        )
        
        self.setWindowTitle("发现新版本")
        self.setWindowIcon(QIcon(":/icons/app/logo.png"))
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.winId()
        set_dark_title_bar(self)
        self._init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        panel_frame = QFrame()
        panel_frame.setObjectName("panelFrame")
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(18, 16, 18, 14)
        panel_layout.setSpacing(12)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("heroIcon")
        self.icon_label.setFixedSize(56, 56)
        self.icon_label.setAlignment(Qt.AlignCenter)
        hero_row.addWidget(self.icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(f"发现新版本 V{self.version_info.version}")
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

        info_frame = QFrame()
        info_frame.setObjectName("metaFrame")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)
        info_layout.addWidget(QLabel(f"当前版本：V{self.current_version}"))
        info_layout.addWidget(QLabel(f"最新版本：V{self.version_info.version}"))
        info_layout.addWidget(QLabel(f"编译日期：{self._format_date(self.version_info.build_date)}"))
        info_layout.addWidget(QLabel(f"文件大小：{self.version_info.file_size_mb} MB"))
        panel_layout.addWidget(info_frame)

        if self._show_change_content:
            divider = QFrame()
            divider.setObjectName("divider")
            divider.setFixedHeight(1)
            panel_layout.addWidget(divider)

            change_scroll = QScrollArea()
            change_scroll.setObjectName("changeScroll")
            change_scroll.setWidgetResizable(True)
            change_scroll.setFrameShape(QFrame.NoFrame)
            change_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            change_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            change_scroll.setMinimumHeight(78)
            change_scroll.setMaximumHeight(78)

            change_label = QLabel()
            change_label.setObjectName("changeTextLabel")
            change_label.setTextFormat(Qt.RichText)
            change_label.setWordWrap(True)
            change_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            change_label.setText(self._build_change_list_html())
            change_label.setContentsMargins(0, 0, 0, 0)

            change_container = QWidget()
            change_container_layout = QVBoxLayout(change_container)
            change_container_layout.setContentsMargins(0, 0, 0, 0)
            change_container_layout.setSpacing(0)
            change_container_layout.addWidget(change_label)
            change_container_layout.addStretch()

            change_scroll.setWidget(change_container)
            panel_layout.addWidget(change_scroll)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        update_btn = QPushButton("立即更新")
        update_btn.setFixedSize(104, 34)
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.setObjectName("primaryButton")
        update_btn.clicked.connect(self._on_update_now)
        button_layout.addWidget(update_btn)

        later_btn = QPushButton("稍后提醒")
        later_btn.setFixedSize(104, 34)
        later_btn.setCursor(Qt.PointingHandCursor)
        later_btn.setObjectName("secondaryButton")
        later_btn.clicked.connect(self._on_remind_later)
        button_layout.addWidget(later_btn)

        skip_btn = QPushButton("跳过此版本")
        skip_btn.setFixedSize(104, 34)
        skip_btn.setCursor(Qt.PointingHandCursor)
        skip_btn.setObjectName("secondaryButton")
        skip_btn.clicked.connect(self._on_skip_version)
        button_layout.addWidget(skip_btn)

        layout.addWidget(panel_frame)
        layout.addLayout(button_layout)
        self._setup_movie()
        self._apply_styles()
        self.setFixedSize(self._dialog_size)
        self.setSizeGripEnabled(False)
    
    def _format_date(self, date_str: str) -> str:
        """格式化日期"""
        try:
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return date_str
        except:
            return date_str

    def _build_subtitle_text(self) -> str:
        if self._show_change_content:
            return "检测到新版本可用，以下内容将在更新后生效。"
        return "检测到新版本可用，可立即下载并准备更新。"

    def _build_change_list_html(self) -> str:
        items = "".join(
            f"<li>{html.escape(item)}</li>"
            for item in self._change_lines[:10]
        )
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        color: {t('text_primary')};
                        font-size: 13px;
                        line-height: 1.5;
                    }}
                    ul {{
                        margin: 0;
                        padding-left: 22px;
                    }}
                    li {{
                        margin: 0 0 5px 0;
                    }}
                    li:last-child {{
                        margin-bottom: 0;
                    }}
                </style>
            </head>
            <body>
                <ul>{items}</ul>
            </body>
        </html>
        """

    def _setup_movie(self):
        movie = QMovie(":/icons/common/running.gif")
        if not movie.isValid():
            self.icon_label.setText("i")
            self.icon_label.setAlignment(Qt.AlignCenter)
            self.icon_label.setObjectName("fallbackIcon")
            return
        movie.setScaledSize(QSize(56, 56))
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
            QFrame#metaFrame {{
                background-color: {t('bg_light')};
                border: 1px solid {t('border')};
                border-radius: 10px;
            }}
            QFrame#divider {{
                background-color: {t('border')};
            }}
            QLabel {{
                color: {t('text_primary')};
                background: transparent;
                border: none;
            }}
            QLabel#heroIcon {{
                background-color: {t('bg_light')};
                border: 1px solid {t('border')};
                border-radius: 12px;
            }}
            QLabel#titleLabel {{
                color: {t('text_primary')};
            }}
            QLabel#subtitleLabel {{
                color: {t('text_secondary')};
                font-size: 13px;
            }}
            QLabel#fallbackIcon {{
                color: {t('status_info')};
                background-color: {t('bg_light')};
                border: 1px solid {t('border')};
                border-radius: 12px;
                font-size: 24px;
                font-weight: 700;
            }}
            QScrollArea#changeScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#changeScroll QWidget {{
                background: transparent;
            }}
            QLabel#changeTextLabel {{
                background-color: transparent;
                color: {t('text_primary')};
                border: none;
                padding: 0px;
                font-size: 13px;
            }}
            QPushButton#primaryButton {{
                min-width: 104px;
            }}
            QPushButton#secondaryButton {{
                min-width: 104px;
            }}
            """
        )
    
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


class UpdateDownloadDialog(AdaptiveDialog):
    """更新下载对话框"""
    
    # 信号
    cancel_download = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        
        self.setWindowTitle("下载更新")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        
        self._init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def _init_ui(self):
        """初始化UI"""
        layout = self.init_dialog_layout(
            (400, 150),
            min_size=(360, 150),
            layout_margins=(20, 20, 20, 20),
            spacing=15,
            max_width_ratio=0.68,
            max_height_ratio=0.50,
        )
        
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
        preferred_height = 270 if self._show_change_content else 205
        self._dialog_size = _compute_fixed_dialog_size(
            parent,
            QSize(500, preferred_height),
            QSize(420, 205),
            0.72,
            0.65,
        )

        self.setWindowTitle("功能变更")
        self.setWindowIcon(QIcon(":/icons/app/logo.png"))
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.winId()
        set_dark_title_bar(self)
        
        self._init_ui()
    
    def showEvent(self, event):
        super().showEvent(event)
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        panel_frame = QFrame()
        panel_frame.setObjectName("panelFrame")
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(18, 16, 18, 14)
        panel_layout.setSpacing(12)

        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 0, 0, 0)
        hero_row.setSpacing(12)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("heroIcon")
        self.icon_label.setFixedSize(56, 56)
        self.icon_label.setAlignment(Qt.AlignCenter)
        hero_row.addWidget(self.icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

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

            change_scroll = QScrollArea()
            change_scroll.setObjectName("changeScroll")
            change_scroll.setWidgetResizable(True)
            change_scroll.setFrameShape(QFrame.NoFrame)
            change_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            change_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            change_scroll.setMinimumHeight(68)
            change_scroll.setMaximumHeight(68)

            change_label = QLabel()
            change_label.setObjectName("changeTextLabel")
            change_label.setTextFormat(Qt.RichText)
            change_label.setWordWrap(True)
            change_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            change_label.setText(self._build_change_list_html())
            change_label.setContentsMargins(0, 0, 0, 0)

            change_container = QWidget()
            change_container_layout = QVBoxLayout(change_container)
            change_container_layout.setContentsMargins(0, 0, 0, 0)
            change_container_layout.setSpacing(0)
            change_container_layout.addWidget(change_label)
            change_container_layout.addStretch()

            change_scroll.setWidget(change_container)
            panel_layout.addWidget(change_scroll)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        restart_btn = QPushButton("立即重启")
        restart_btn.setFixedSize(116, 34)
        restart_btn.setCursor(Qt.PointingHandCursor)
        restart_btn.setObjectName("primaryButton")
        restart_btn.clicked.connect(self._on_restart_now)
        button_layout.addWidget(restart_btn)

        layout.addWidget(panel_frame)
        layout.addLayout(button_layout)
        self._setup_movie()
        self._apply_styles()
        self._dialog_size = QSize(self._dialog_size.width(), 270 if self._show_change_content else self._dialog_size.height())
        self.setFixedSize(self._dialog_size)
        self.setSizeGripEnabled(False)

    def _build_subtitle_text(self) -> str:
        if self._show_change_content:
            return "检测到下列功能变更，重启程序以应用"
        return "检测到功能变更，重启程序以应用"

    def _build_change_list_html(self) -> str:
        items = "".join(
            f"<li>{html.escape(item)}</li>"
            for item in self._change_lines[:10]
        )
        return f"""
        <html>
            <head>
                <style>
                    body {{
                        margin: 0;
                        color: {t('text_primary')};
                        font-size: 13px;
                        line-height: 1.5;
                    }}
                    ul {{
                        margin: 0;
                        padding-left: 22px;
                    }}
                    li {{
                        margin: 0 0 5px 0;
                    }}
                    li:last-child {{
                        margin-bottom: 0;
                    }}
                </style>
            </head>
            <body>
                <ul>{items}</ul>
            </body>
        </html>
        """

    def _setup_movie(self):
        movie = QMovie(":/icons/common/running.gif")
        if not movie.isValid():
            self.icon_label.setText("i")
            self.icon_label.setAlignment(Qt.AlignCenter)
            self.icon_label.setObjectName("fallbackIcon")
            return
        movie.setScaledSize(QSize(56, 56))
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
            QScrollArea#changeScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#changeScroll QWidget {{
                background: transparent;
            }}
            QLabel#changeTextLabel {{
                background-color: transparent;
                color: {t('text_primary')};
                border: none;
                padding: 0px;
                font-size: 13px;
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
