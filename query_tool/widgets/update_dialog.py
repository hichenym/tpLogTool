"""
更新对话框
"""
import html
import resources.icon_res as icon_res
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QCursor, QFont, QIcon, QMovie

from query_tool.ui import (
    BodyLabel,
    ElevatedCardWidget,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    ScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
)
from query_tool.utils import StyleManager
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.utils.update_checker import VersionInfo
from query_tool.utils.theme_manager import t, theme_manager


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


def _apply_text_label_style(label, *, color_role="text_primary", font_size=None, font_weight=None):
    rules = [
        f"color: {t(color_role)}",
        "background: transparent",
        "border: none",
    ]
    if font_size is not None:
        rules.append(f"font-size: {font_size}px")
    if font_weight is not None:
        rules.append(f"font-weight: {font_weight}")
    label.setStyleSheet("; ".join(rules) + ";")


def _apply_card_style(widget, *, object_name=None, background_role="bg_mid", radius=14):
    if QFLUENT_WIDGETS_AVAILABLE:
        widget.setStyleSheet("")
        return

    selector = f"#{object_name or widget.objectName()}" if (object_name or widget.objectName()) else "QFrame"
    widget.setStyleSheet(
        f"""
        {selector} {{
            background-color: {t(background_role)};
            border: 1px solid {t('border')};
            border-radius: {radius}px;
        }}
        """
    )


def _apply_primary_button_style(button):
    if QFLUENT_WIDGETS_AVAILABLE:
        button.setStyleSheet("")
        return

    button.setStyleSheet(
        f"""
        QPushButton {{
            border-radius: 8px;
            padding: 0 18px;
            font-size: 13px;
            background-color: {t('accent')};
            color: #ffffff;
            border: 1px solid {t('accent')};
        }}
        QPushButton:hover {{
            background-color: {t('accent_dim')};
            border: 1px solid {t('accent_dim')};
        }}
        QPushButton:pressed {{
            background-color: {t('accent_dim')};
        }}
        QPushButton:disabled {{
            background-color: {t('bg_mid')};
            color: {t('text_disabled')};
            border: 1px solid {t('border_dark')};
        }}
        """
    )


def _apply_secondary_button_style(button):
    if QFLUENT_WIDGETS_AVAILABLE:
        button.setStyleSheet("")
        return
    button.setStyleSheet(StyleManager.get_ACTION_BUTTON())


def _apply_transparent_scroll_style(scroll_area):
    scroll_area.setStyleSheet(
        f"""
        QScrollArea {{
            background: transparent;
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QScrollBar:vertical {{
            background-color: transparent;
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {t('border_hover')};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        """
    )


def _apply_fallback_icon_style(label, *, boxed):
    if boxed:
        label.setStyleSheet(
            f"""
            background-color: {t('bg_light')};
            border: 1px solid {t('border')};
            border-radius: 12px;
            color: {t('status_info')};
            font-size: 24px;
            font-weight: 700;
            """
        )
        return

    label.setStyleSheet(
        f"""
        background: transparent;
        border: none;
        color: {t('status_info')};
        font-size: 24px;
        font-weight: 700;
        """
    )


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
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)
        set_dark_title_bar(self)
        self._init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass
    
    def _init_ui(self):
        """初始化UI"""
        self.info_labels = []

        layout = self.init_dialog_layout(
            self._dialog_size,
            min_size=(460, 300),
            layout_margins=(16, 14, 16, 14),
            spacing=10,
            max_width_ratio=0.78,
            max_height_ratio=0.82,
        )

        self.panel_frame = ElevatedCardWidget(self)
        self.panel_frame.setObjectName("updatePromptPanel")
        panel_layout = QVBoxLayout(self.panel_frame)
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

        self.title_label = StrongBodyLabel(f"发现新版本 V{self.version_info.version}")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        text_layout.addWidget(self.title_label)

        self.subtitle_label = SubtitleLabel(self._build_subtitle_text())
        self.subtitle_label.setWordWrap(True)
        text_layout.addWidget(self.subtitle_label)
        hero_row.addLayout(text_layout, 1)
        panel_layout.addLayout(hero_row)

        self.meta_frame = ElevatedCardWidget(self.panel_frame)
        self.meta_frame.setObjectName("updatePromptMeta")
        info_layout = QVBoxLayout(self.meta_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)
        info_layout.addWidget(self._info_label(f"当前版本：V{self.current_version}"))
        info_layout.addWidget(self._info_label(f"最新版本：V{self.version_info.version}"))
        info_layout.addWidget(self._info_label(f"编译日期：{self._format_date(self.version_info.build_date)}"))
        info_layout.addWidget(self._info_label(f"文件大小：{self.version_info.file_size_mb} MB"))
        panel_layout.addWidget(self.meta_frame)

        if self._show_change_content:
            self.divider = QFrame()
            self.divider.setFixedHeight(1)
            panel_layout.addWidget(self.divider)

            self.change_scroll = ScrollArea()
            self.change_scroll.setWidgetResizable(True)
            self.change_scroll.setFrameShape(QFrame.NoFrame)
            self.change_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.change_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.change_scroll.setMinimumHeight(78)
            self.change_scroll.setMaximumHeight(78)

            self.change_label = QLabel()
            self.change_label.setTextFormat(Qt.RichText)
            self.change_label.setWordWrap(True)
            self.change_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.change_label.setContentsMargins(0, 0, 0, 0)

            change_container = QWidget()
            change_container_layout = QVBoxLayout(change_container)
            change_container_layout.setContentsMargins(0, 0, 0, 0)
            change_container_layout.setSpacing(0)
            change_container_layout.addWidget(self.change_label)
            change_container_layout.addStretch()

            self.change_scroll.setWidget(change_container)
            panel_layout.addWidget(self.change_scroll)
        else:
            self.divider = None
            self.change_scroll = None
            self.change_label = None

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        self.update_btn = PrimaryPushButton("立即更新")
        self.update_btn.setFixedSize(104, 34)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self._on_update_now)
        button_layout.addWidget(self.update_btn)

        self.later_btn = PushButton("稍后提醒")
        self.later_btn.setFixedSize(104, 34)
        self.later_btn.setCursor(Qt.PointingHandCursor)
        self.later_btn.clicked.connect(self._on_remind_later)
        button_layout.addWidget(self.later_btn)

        self.skip_btn = PushButton("跳过此版本")
        self.skip_btn.setFixedSize(104, 34)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.clicked.connect(self._on_skip_version)
        button_layout.addWidget(self.skip_btn)

        layout.addWidget(self.panel_frame)
        layout.addLayout(button_layout)
        self._setup_movie()
        self.refresh_theme()
        self.apply_adaptive_geometry()
        self.lock_size_to_current()

    def _info_label(self, text):
        label = BodyLabel(text)
        self.info_labels.append(label)
        return label
    
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
            return
        movie.setScaledSize(QSize(56, 56))
        self._icon_movie = movie
        self.icon_label.setMovie(movie)
        movie.start()

    def _apply_styles(self):
        _apply_card_style(self.panel_frame, object_name="updatePromptPanel", background_role="bg_mid", radius=14)
        _apply_card_style(self.meta_frame, object_name="updatePromptMeta", background_role="bg_light", radius=10)
        _apply_text_label_style(self.title_label, font_weight=600)
        _apply_text_label_style(self.subtitle_label, color_role="text_secondary", font_size=13)
        for label in self.info_labels:
            _apply_text_label_style(label)
        if self.divider is not None:
            self.divider.setStyleSheet(f"background-color: {t('border')}; border: none;")
        if self.change_scroll is not None:
            _apply_transparent_scroll_style(self.change_scroll)
        if self.change_label is not None:
            _apply_text_label_style(self.change_label, font_size=13)
            self.change_label.setText(self._build_change_list_html())
        _apply_primary_button_style(self.update_btn)
        _apply_secondary_button_style(self.later_btn)
        _apply_secondary_button_style(self.skip_btn)

        if self._icon_movie is None:
            _apply_fallback_icon_style(self.icon_label, boxed=True)
        else:
            self.icon_label.setStyleSheet(
                f"""
                background-color: {t('bg_light')};
                border: 1px solid {t('border')};
                border-radius: 12px;
                """
            )

    def refresh_theme(self):
        self._apply_styles()
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


class UpdateDownloadDialog(AdaptiveDialog):
    """更新下载对话框"""
    
    # 信号
    cancel_download = pyqtSignal()
    
    def __init__(self, version_info: VersionInfo, parent=None):
        super().__init__(parent)
        
        self.version_info = version_info
        
        self.setWindowTitle("下载更新")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)
        
        self._init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass
    
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
        title_label = StrongBodyLabel(f"正在下载 V{self.version_info.version}")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 进度条
        self.progress_bar = ProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = BodyLabel("准备下载...")
        layout.addWidget(self.status_label)
        
        # 取消按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = PushButton("取消")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)

    def refresh_theme(self):
        set_dark_title_bar(self)
    
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


class UpdateCompleteDialog(AdaptiveDialog):
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
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.winId()
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)
        set_dark_title_bar(self)
        
        self._init_ui()
    
    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass
    
    def _init_ui(self):
        """初始化UI"""
        layout = self.init_dialog_layout(
            self._dialog_size,
            min_size=(420, 205),
            layout_margins=(16, 14, 16, 14),
            spacing=10,
            max_width_ratio=0.72,
            max_height_ratio=0.65,
        )

        self.panel_frame = ElevatedCardWidget(self)
        self.panel_frame.setObjectName("updateCompletePanel")
        panel_layout = QVBoxLayout(self.panel_frame)
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

        self.title_label = StrongBodyLabel("检测到功能变更")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setObjectName("titleLabel")
        text_layout.addWidget(self.title_label)

        self.subtitle_label = SubtitleLabel(self._build_subtitle_text())
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setObjectName("subtitleLabel")
        text_layout.addWidget(self.subtitle_label)
        hero_row.addLayout(text_layout, 1)
        panel_layout.addLayout(hero_row)

        if self._show_change_content:
            self.divider = QFrame()
            self.divider.setFixedHeight(1)
            panel_layout.addWidget(self.divider)

            self.change_scroll = ScrollArea()
            self.change_scroll.setWidgetResizable(True)
            self.change_scroll.setFrameShape(QFrame.NoFrame)
            self.change_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.change_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.change_scroll.setMinimumHeight(68)
            self.change_scroll.setMaximumHeight(68)

            self.change_label = QLabel()
            self.change_label.setTextFormat(Qt.RichText)
            self.change_label.setWordWrap(True)
            self.change_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.change_label.setText(self._build_change_list_html())
            self.change_label.setContentsMargins(0, 0, 0, 0)

            change_container = QWidget()
            change_container_layout = QVBoxLayout(change_container)
            change_container_layout.setContentsMargins(0, 0, 0, 0)
            change_container_layout.setSpacing(0)
            change_container_layout.addWidget(self.change_label)
            change_container_layout.addStretch()

            self.change_scroll.setWidget(change_container)
            panel_layout.addWidget(self.change_scroll)
        else:
            self.divider = None
            self.change_scroll = None
            self.change_label = None
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        self.restart_btn = PrimaryPushButton("立即重启")
        self.restart_btn.setFixedSize(116, 34)
        self.restart_btn.setCursor(Qt.PointingHandCursor)
        self.restart_btn.clicked.connect(self._on_restart_now)
        button_layout.addWidget(self.restart_btn)

        layout.addWidget(self.panel_frame)
        layout.addLayout(button_layout)
        self._setup_movie()
        self._dialog_size = QSize(self._dialog_size.width(), 270 if self._show_change_content else self._dialog_size.height())
        self.refresh_theme()
        self.apply_adaptive_geometry()

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
            return
        movie.setScaledSize(QSize(56, 56))
        self._icon_movie = movie
        self.icon_label.setMovie(movie)
        movie.start()

    def _apply_styles(self):
        _apply_card_style(self.panel_frame, object_name="updateCompletePanel", background_role="bg_mid", radius=14)
        _apply_text_label_style(self.title_label, font_weight=600)
        _apply_text_label_style(self.subtitle_label, color_role="text_secondary", font_size=12)
        if self.divider is not None:
            self.divider.setStyleSheet(f"background-color: {t('border')}; border: none;")
        if self.change_scroll is not None:
            _apply_transparent_scroll_style(self.change_scroll)
        if self.change_label is not None:
            _apply_text_label_style(self.change_label, font_size=13)
            self.change_label.setText(self._build_change_list_html())
        _apply_primary_button_style(self.restart_btn)

        if self._icon_movie is None:
            _apply_fallback_icon_style(self.icon_label, boxed=False)
        else:
            self.icon_label.setStyleSheet("background: transparent; border: none;")
    
    def refresh_theme(self):
        self._apply_styles()
        set_dark_title_bar(self)
    
    def _on_restart_now(self):
        """立即重启"""
        self.restart_now.emit()
        self.accept()
