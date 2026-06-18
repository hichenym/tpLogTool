"""
GitLab 日志导出页面
提供 GitLab 提交日志查询和导出功能
"""
import os
from collections import OrderedDict
from datetime import datetime
from PyQt5.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLineEdit, QPlainTextEdit,
    QShortcut, QSizePolicy, QTextEdit, QVBoxLayout, QWidget
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QSize, QEvent
from PyQt5.QtGui import QFontMetrics, QIcon, QTextCursor, QTextDocument, QKeySequence, QColor, QTextCharFormat

from .base_page import BasePage
from .page_registry import register_page
from query_tool.ui import (
    BodyLabel,
    DateEdit,
    EditableComboBox,
    ElevatedCardWidget,
    LineEdit,
    PasswordLineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    ScrollArea,
    StrongBodyLabel,
)
from query_tool.utils import ButtonManager, ThreadManager
from query_tool.utils.style_manager import StyleManager
from query_tool.utils.gitlab_api import GitLabAPI
from query_tool.utils.excel_helper import create_gitlab_xlsx
from query_tool.utils.theme_manager import t
from query_tool.widgets import ClickableLineEdit


class GitLabWorkerThread(QThread):
    """GitLab 后台工作线程"""
    finished_signal = pyqtSignal(object)
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)
    
    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
    
    def run(self):
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished_signal.emit(result)
        except Exception as e:
            self.error_signal.emit(str(e))


class SearchablePlainTextEdit(PlainTextEdit):
    """支持快捷搜索的纯文本框"""
    find_requested = pyqtSignal()
    find_next_requested = pyqtSignal()
    find_previous_requested = pyqtSignal()
    
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Find):
            self.find_requested.emit()
            event.accept()
            return
        if event.matches(QKeySequence.FindNext):
            self.find_next_requested.emit()
            event.accept()
            return
        if event.matches(QKeySequence.FindPrevious):
            self.find_previous_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


@register_page("GIT", order=6, icon=":/icons/system/git.png")
class GitLabLogPage(BasePage):
    """GitLab 日志导出页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "GIT"
        self._cards = []
        self._card_title_labels = []
        
        # 管理器
        self.btn_manager = ButtonManager()
        self.thread_mgr = ThreadManager()
        
        # 数据
        self.api = None
        self.projects = []
        self.branches = []
        self.is_connected = False
        self.current_project = None
        
        # 配置
        self.gitlab_server = ""
        self.gitlab_token = ""
        self.save_path = ""
        self.recent_projects = []
        self.recent_branches = {}
        self.query_conditions_collapsed = False
        self.last_search_keyword = ""
        self.base_commits_cache = OrderedDict()
        self.hydrated_commits_cache = OrderedDict()
        self.authors_cache = OrderedDict()
        
        self.init_ui()
        self.load_config()

    def _apply_card_title_style(self, label):
        label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")

    def _apply_card_style(self, card):
        if not QFLUENT_WIDGETS_AVAILABLE:
            card.setStyleSheet(
                f"""
                #{card.objectName()} {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )

    def _create_card_section(self, title, vertical_policy=QSizePolicy.Fixed):
        """创建统一样式的 Fluent 卡片区域。"""
        card = ElevatedCardWidget(self)
        card.setObjectName(f"gitlabCard{len(self._cards) + 1}")
        self._cards.append(card)
        card.setSizePolicy(QSizePolicy.Expanding, vertical_policy)
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        title_label = StrongBodyLabel(title)
        self._card_title_labels.append(title_label)
        self._apply_card_title_style(title_label)
        layout.addWidget(title_label)
        self._apply_card_style(card)
        return card, layout

    def _create_subsection_card(self, title, vertical_policy=QSizePolicy.Expanding):
        card = ElevatedCardWidget(self)
        card.setObjectName(f"gitlabSubCard{len(self._cards) + 1}")
        self._cards.append(card)
        card.setSizePolicy(QSizePolicy.Expanding, vertical_policy)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        title_label = BodyLabel(title)
        self._card_title_labels.append(title_label)
        self._apply_card_title_style(title_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        self._apply_card_style(card)
        return card, layout, header_layout

    @staticmethod
    def _combo_line_edit(combo):
        """兼容获取可编辑下拉框内部输入框。"""
        getter = getattr(combo, "lineEdit", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

    def _set_combo_placeholder(self, combo, text):
        """兼容设置下拉框占位文字。"""
        setter = getattr(combo, "setPlaceholderText", None)
        if callable(setter):
            try:
                setter(text)
                return
            except Exception:
                pass

        line_edit = self._combo_line_edit(combo)
        if line_edit is not None:
            line_edit.setPlaceholderText(text)

    def _set_combo_visual_state(self, combo, active):
        """在非 Fluent 回退模式下保留旧的激活态提示。"""
        if QFLUENT_WIDGETS_AVAILABLE:
            return

        line_edit = self._combo_line_edit(combo)
        if line_edit is None:
            return

        style = (
            StyleManager.get_COMBO_LINE_EDIT_ACTIVE()
            if active else
            StyleManager.get_COMBO_LINE_EDIT_INACTIVE()
        )
        line_edit.setStyleSheet(style)

    def _configure_combo(self, combo, placeholder=""):
        """初始化可搜索下拉框的通用行为。"""
        combo.setMinimumHeight(self._control_height())
        combo.setFocusPolicy(Qt.StrongFocus)
        combo.wheelEvent = lambda event: event.ignore()

        if hasattr(combo, "setEditable"):
            try:
                combo.setEditable(True)
            except Exception:
                pass

        if hasattr(combo, "setInsertPolicy"):
            no_insert = getattr(type(combo), "NoInsert", getattr(combo, "NoInsert", None))
            if no_insert is not None:
                try:
                    combo.setInsertPolicy(no_insert)
                except Exception:
                    pass

        self._set_combo_placeholder(combo, placeholder)
        self._set_combo_visual_state(combo, active=False)

    def _control_height(self, extra_padding: int = 12, minimum: int = 32) -> int:
        metrics = QFontMetrics(self.font())
        return max(minimum, metrics.height() + extra_padding)

    def _form_label_width(self) -> int:
        metrics = QFontMetrics(self.font())
        return max(70, metrics.horizontalAdvance("保存路径:") + 14)

    def init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 使用滚动区域
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area = scroll
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        self.content_widget = content_widget
        self.content_layout = content_layout
        
        # 1. 服务器连接区
        self.create_connection_area(content_layout)
        
        # 2. 查询条件区
        self.create_query_area(content_layout)
        
        # 3. 时间范围和导出区
        self.create_export_area(content_layout)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # 创建按钮组
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(
            self.connect_btn, self.browse_btn, self.export_btn, self.query_btn
        )
        self.scroll_area.viewport().installEventFilter(self)
        
        # 初始状态
        self.set_controls_enabled(False)
        self._lock_static_group_heights()
        self._update_result_area_height()
    
    def create_connection_area(self, parent_layout):
        """创建服务器连接区域"""
        self.connection_group, layout = self._create_card_section("服务器连接")
        label_width = self._form_label_width()
        control_height = self._control_height()

        # 服务器地址
        server_layout = QHBoxLayout()
        server_label = BodyLabel("服务器:")
        server_label.setFixedWidth(label_width)
        server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.server_input = LineEdit()
        self.server_input.setPlaceholderText("https://gitlab.example.com")
        self.server_input.setMinimumHeight(control_height)
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_input, 1)
        layout.addLayout(server_layout)

        # Token
        token_layout = QHBoxLayout()
        token_label = BodyLabel("Token:")
        token_label.setFixedWidth(label_width)
        token_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.token_input = PasswordLineEdit()
        self.token_input.setPlaceholderText("请输入 GitLab Token")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setMinimumHeight(control_height)

        self.connect_btn = PrimaryPushButton("连接")
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/connect.png"))
        self.connect_btn.setIconSize(QSize(16, 16))
        self.connect_btn.setMinimumWidth(96)
        self.connect_btn.setFixedHeight(control_height)
        self.connect_btn.clicked.connect(self.on_connect)

        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input, 1)
        token_layout.addWidget(self.connect_btn)
        layout.addLayout(token_layout)
        
        parent_layout.addWidget(self.connection_group)
    
    def create_query_area(self, parent_layout):
        """创建查询条件区域"""
        self.query_group, layout = self._create_card_section("查询条件")
        label_width = self._form_label_width()
        control_height = self._control_height()

        # 项目
        project_layout = QHBoxLayout()
        project_label = BodyLabel("项目:")
        project_label.setFixedWidth(label_width)
        project_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.project_combo = EditableComboBox()
        self._configure_combo(self.project_combo)
        self.project_combo.activated.connect(
            lambda *_args: self.on_project_selected(self.project_combo.currentIndex())
        )
        project_layout.addWidget(project_label)
        project_layout.addWidget(self.project_combo, 1)
        layout.addLayout(project_layout)

        # 分支
        branch_layout = QHBoxLayout()
        branch_label = BodyLabel("分支:")
        branch_label.setFixedWidth(label_width)
        branch_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.branch_combo = EditableComboBox()
        self._configure_combo(self.branch_combo)
        branch_layout.addWidget(branch_label)
        branch_layout.addWidget(self.branch_combo, 1)
        layout.addLayout(branch_layout)

        # 提交者
        author_layout = QHBoxLayout()
        author_label = BodyLabel("提交者:")
        author_label.setFixedWidth(label_width)
        author_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.author_combo = EditableComboBox()
        self._configure_combo(self.author_combo)
        author_layout.addWidget(author_label)
        author_layout.addWidget(self.author_combo, 1)
        layout.addLayout(author_layout)

        # 关键词
        keyword_layout = QHBoxLayout()
        keyword_label = BodyLabel("关键词:")
        keyword_label.setFixedWidth(label_width)
        keyword_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.keyword_input = LineEdit()
        self.keyword_input.setPlaceholderText("多个关键词用分号隔开，导出后高亮")
        self.keyword_input.setMinimumHeight(control_height)
        keyword_layout.addWidget(keyword_label)
        keyword_layout.addWidget(self.keyword_input, 1)
        layout.addLayout(keyword_layout)
        
        parent_layout.addWidget(self.query_group)
    
    def create_export_area(self, parent_layout):
        """创建时间范围和导出区域"""
        self.export_group, layout = self._create_card_section("时间范围与导出")
        label_width = self._form_label_width()
        control_height = self._control_height()

        # 时间范围（水平排列）
        time_layout = QHBoxLayout()

        # 开始时间
        start_label = BodyLabel("开始时间:")
        start_label.setFixedWidth(label_width)
        start_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.start_date = DateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setMinimumHeight(control_height)
        time_layout.addWidget(start_label)
        time_layout.addWidget(self.start_date, 1)
        
        # 添加间距
        time_layout.addSpacing(20)

        # 结束时间
        end_label = BodyLabel("结束时间:")
        end_label.setFixedWidth(label_width)
        end_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.end_date = DateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setMinimumHeight(control_height)
        time_layout.addWidget(end_label)
        time_layout.addWidget(self.end_date, 1)
        
        layout.addLayout(time_layout)

        # 保存路径
        path_layout = QHBoxLayout()
        path_label = BodyLabel("保存路径:")
        path_label.setFixedWidth(label_width)
        path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.path_input = ClickableLineEdit()
        self.path_input.setPlaceholderText("点击浏览选择保存目录（双击可打开目录）")
        self.path_input.setReadOnly(True)
        self.path_input.setFocusPolicy(Qt.NoFocus)
        self.path_input.setMinimumHeight(control_height)

        self.browse_btn = PushButton("浏览")
        self.browse_btn.setIcon(QIcon(":/icons/gitlab/browser.png"))
        self.browse_btn.setIconSize(QSize(16, 16))
        self.browse_btn.setMinimumWidth(96)
        self.browse_btn.setFixedHeight(control_height)
        self.browse_btn.clicked.connect(self.on_browse)

        self.export_btn = PushButton("导出")
        self.export_btn.setIcon(QIcon(":/icons/gitlab/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setMinimumWidth(96)
        self.export_btn.setFixedHeight(control_height)
        self.export_btn.clicked.connect(self.on_export)

        self.query_btn = PrimaryPushButton("查询")
        self.query_btn.setMinimumWidth(96)
        self.query_btn.setFixedHeight(control_height)
        self.query_btn.clicked.connect(self.on_query)

        self.toggle_conditions_btn = PushButton("收起")
        self.toggle_conditions_btn.setMinimumWidth(96)
        self.toggle_conditions_btn.setFixedHeight(control_height)
        self.toggle_conditions_btn.clicked.connect(self.toggle_query_conditions)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input, 1)
        path_layout.addWidget(self.browse_btn)
        path_layout.addWidget(self.export_btn)
        path_layout.addWidget(self.query_btn)
        path_layout.addWidget(self.toggle_conditions_btn)
        layout.addLayout(path_layout)
        
        parent_layout.addWidget(self.export_group)

        self.create_result_area(parent_layout)

    def create_result_area(self, parent_layout):
        """创建查询结果区域"""
        self.result_group, layout = self._create_card_section("Git 记录", QSizePolicy.Expanding)
        self.result_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.search_card, search_card_layout, _search_header_layout = self._create_subsection_card("快速搜索", QSizePolicy.Fixed)
        self.search_bar = QWidget()
        self.search_bar.setVisible(False)
        self.search_card.setVisible(False)
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)

        search_label = BodyLabel("搜索:")
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("输入关键字后回车，支持 Ctrl+F / F3 / Shift+F3")
        self.search_input.setMinimumHeight(self._control_height())
        self.search_input.returnPressed.connect(self.find_next_in_result)
        self.search_input.textChanged.connect(self.update_search_highlights)

        self.prev_match_btn = PushButton("上一条")
        self.prev_match_btn.setMinimumWidth(96)
        self.prev_match_btn.setFixedHeight(self._control_height())
        self.prev_match_btn.clicked.connect(self.find_previous_in_result)

        self.next_match_btn = PushButton("下一条")
        self.next_match_btn.setMinimumWidth(96)
        self.next_match_btn.setFixedHeight(self._control_height())
        self.next_match_btn.clicked.connect(self.find_next_in_result)

        self.close_search_btn = PushButton("关闭搜索")
        self.close_search_btn.setMinimumWidth(108)
        self.close_search_btn.setFixedHeight(self._control_height())
        self.close_search_btn.clicked.connect(self.hide_search_bar)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.prev_match_btn)
        search_layout.addWidget(self.next_match_btn)
        search_layout.addWidget(self.close_search_btn)
        search_card_layout.addWidget(self.search_bar)
        layout.addWidget(self.search_card)

        self.result_text_card, result_text_layout, _result_text_header_layout = self._create_subsection_card("提交记录", QSizePolicy.Expanding)
        self.result_text = SearchablePlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.result_text.setMinimumHeight(260)
        self.result_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_text.setPlaceholderText("点击“查询”后，这里会展示 Git 提交记录。")
        self.result_text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        if not QFLUENT_WIDGETS_AVAILABLE:
            self.result_text.setStyleSheet(StyleManager.get_PLAINTEXT_EDIT_TABLE())
        self.result_text.find_requested.connect(self.show_search_bar)
        self.result_text.find_next_requested.connect(self.find_next_in_result)
        self.result_text.find_previous_requested.connect(self.find_previous_in_result)
        result_text_layout.addWidget(self.result_text)
        layout.addWidget(self.result_text_card, 1)

        self.find_shortcut = QShortcut(QKeySequence.Find, self.result_group)
        self.find_shortcut.activated.connect(self.show_search_bar)

        parent_layout.addWidget(self.result_group)
        if hasattr(self, 'content_layout'):
            self.content_layout.setStretchFactor(self.result_group, 1)

    def _lock_static_group_heights(self):
        """锁定顶部筛选区域高度，避免随窗口拉伸"""
        for group in (self.connection_group, self.query_group, self.export_group):
            height = max(group.minimumSizeHint().height(), group.sizeHint().height())
            group.setMinimumHeight(height)
            group.setMaximumHeight(height)

    def eventFilter(self, watched, event):
        if hasattr(self, 'scroll_area') and watched is self.scroll_area.viewport():
            if event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
                self._update_result_area_height()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_result_area_height()

    def _sum_visible_group_heights(self, widgets):
        """计算可见分组高度之和"""
        visible_widgets = [widget for widget in widgets if widget.isVisible()]
        if not visible_widgets:
            return 0
        return (
            sum(widget.sizeHint().height() for widget in visible_widgets)
            + max(0, len(visible_widgets) - 1) * self.content_layout.spacing()
        )

    def _update_result_area_height(self):
        """根据窗口高度自动调整 Git 记录区高度"""
        if not hasattr(self, 'scroll_area') or not hasattr(self, 'result_group'):
            return

        viewport_height = self.scroll_area.viewport().height()
        margins = self.content_layout.contentsMargins()
        used_height = margins.top() + margins.bottom()
        used_height += self._sum_visible_group_heights([
            self.connection_group,
            self.query_group,
            self.export_group
        ])
        used_height += self.content_layout.spacing()

        available_height = max(320, viewport_height - used_height)
        self.result_group.setMinimumHeight(available_height)

    def update_search_highlights(self):
        """更新搜索高亮"""
        if not hasattr(self, 'result_text'):
            return

        keyword = self.search_input.text().strip()
        selections = []

        if keyword:
            document = self.result_text.document()
            cursor = QTextCursor(document)
            normal_format = QTextCharFormat()
            normal_format.setBackground(QColor("#8a6d00"))
            normal_format.setForeground(QColor("#fff7bf"))

            while True:
                cursor = document.find(keyword, cursor)
                if cursor.isNull():
                    break
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = normal_format
                selections.append(selection)

        current_cursor = self.result_text.textCursor()
        if keyword and current_cursor.hasSelection() and current_cursor.selectedText() == keyword:
            current_format = QTextCharFormat()
            current_format.setBackground(QColor("#d8a300"))
            current_format.setForeground(QColor("#1f1f1f"))
            current_selection = QTextEdit.ExtraSelection()
            current_selection.cursor = current_cursor
            current_selection.format = current_format
            selections.append(current_selection)

        self.result_text.setExtraSelections(selections)

    
    def set_controls_enabled(self, enabled):
        """设置控件启用状态"""
        self.project_combo.setEnabled(enabled)
        self.branch_combo.setEnabled(enabled)
        self.author_combo.setEnabled(enabled)
        self.keyword_input.setEnabled(enabled)
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        self.export_btn.setEnabled(enabled)
        self.query_btn.setEnabled(enabled)
    
    def on_connect(self):
        """连接/断开服务器"""
        if self.is_connected:
            self.disconnect_server()
            return
        
        server = self.server_input.text().strip()
        token = self.token_input.text().strip()
        
        if not server or not token:
            self.show_warning("请填写服务器地址和Token")
            return
        
        self.show_progress(f"正在连接服务器: {server}")
        self.connect_btn.setEnabled(False)
        self.server_input.setEnabled(False)
        self.token_input.setEnabled(False)
        
        self.api = GitLabAPI(server, token)
        thread = GitLabWorkerThread(self.api.get_all_projects)
        thread.finished_signal.connect(self.on_projects_loaded)
        thread.error_signal.connect(self.on_connect_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("connect", thread)
        thread.start()
    
    def disconnect_server(self):
        """断开服务器连接"""
        self.api = None
        self.is_connected = False
        self.projects = []
        self.branches = []
        self.base_commits_cache.clear()
        self.hydrated_commits_cache.clear()
        self.authors_cache.clear()
        
        # 更新按钮
        self.connect_btn.setText("连接")
        self.main_buttons.set_text(self.connect_btn, "连接")
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/connect.png"))
        
        # 清空并禁用控件
        self.project_combo.clear()
        self.branch_combo.clear()
        self.author_combo.clear()

        # 清空占位文字
        self._set_combo_placeholder(self.project_combo, "")
        self._set_combo_placeholder(self.branch_combo, "")
        self._set_combo_placeholder(self.author_combo, "")
        self._set_combo_visual_state(self.project_combo, active=False)
        self._set_combo_visual_state(self.branch_combo, active=False)
        self._set_combo_visual_state(self.author_combo, active=False)

        self.set_controls_enabled(False)
        self.result_text.clear()
        self.result_text.setExtraSelections([])
        self.search_input.clear()
        self.last_search_keyword = ""
        self.search_bar.setVisible(False)
        self.result_text.setPlaceholderText("点击“查询”后，这里会展示 Git 提交记录。")
        self._update_result_area_height()
        
        # 启用输入框
        self.server_input.setEnabled(True)
        self.token_input.setEnabled(True)
        
        self.show_info("已断开服务器连接")
    
    def on_projects_loaded(self, projects):
        """项目列表加载完成"""
        self.projects = projects
        self.is_connected = True
        
        self.show_success(f"连接成功! 获取到 {len(projects)} 个项目")
        
        # 更新按钮
        self.connect_btn.setText("断开")
        self.main_buttons.set_text(self.connect_btn, "断开")
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/disconnect.png"))
        self.connect_btn.setEnabled(True)

        self._set_combo_visual_state(self.project_combo, active=True)
        self._set_combo_placeholder(self.project_combo, "请选择或输入项目名...")

        # 填充项目列表
        self.project_combo.clear()

        # 添加最近使用的项目
        added_recent = set()
        for rp in self.recent_projects:
            if any(p['path_with_namespace'] == rp for p in projects):
                self.project_combo.addItem(f"★ {rp}", rp)
                added_recent.add(rp)

        # 添加所有项目
        for p in projects:
            path = p['path_with_namespace']
            if path not in added_recent:
                self.project_combo.addItem(path, path)
        
        self.project_combo.setCurrentIndex(-1)
        self.project_combo.setEnabled(True)
        
        # 保存配置
        self.save_config()
    
    def on_connect_error(self, error):
        """连接失败"""
        self.show_error(f"连接失败: {error}")
        self.connect_btn.setEnabled(True)
        self.server_input.setEnabled(True)
        self.token_input.setEnabled(True)

    def toggle_query_conditions(self):
        """收起/展开服务器连接和查询条件区域"""
        self.query_conditions_collapsed = not self.query_conditions_collapsed
        self.connection_group.setVisible(not self.query_conditions_collapsed)
        self.query_group.setVisible(not self.query_conditions_collapsed)
        self.toggle_conditions_btn.setText("展开" if self.query_conditions_collapsed else "收起")
        self._update_result_area_height()
    
    def on_project_selected(self, index):
        """项目选择"""
        if index < 0:
            return
        
        project_path = self.project_combo.currentData()
        if not project_path:
            project_path = self.project_combo.currentText().replace("★ ", "")
        
        if not project_path:
            return
        
        self.current_project = project_path
        self.show_progress(f"正在获取项目 [{project_path}] 的分支...")
        
        self.project_combo.setEnabled(False)
        self.branch_combo.clear()
        self.branch_combo.setEnabled(False)
        self.set_controls_enabled(False)
        
        thread = GitLabWorkerThread(self.api.get_branches, project_path)
        thread.finished_signal.connect(self.on_branches_loaded)
        thread.error_signal.connect(self.on_branch_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("branches", thread)
        thread.start()
    
    def on_branches_loaded(self, branches):
        """分支列表加载完成"""
        self.branches = branches
        self.show_success(f"获取到 {len(branches)} 个分支")

        self._set_combo_visual_state(self.branch_combo, active=True)
        self._set_combo_placeholder(self.branch_combo, "请选择或输入分支名...")

        self.branch_combo.clear()
        
        # 默认分支放前面
        default_branch = next((b for b in branches if b.get('default')), None)
        if default_branch:
            branches.remove(default_branch)
            branches.insert(0, default_branch)
        
        # 获取最近使用的分支
        recent_branches = self.recent_branches.get(self.current_project, [])
        added_recent = set()

        for rb in recent_branches:
            if any(b['name'] == rb for b in branches):
                self.branch_combo.addItem(f"★ {rb}", rb)
                added_recent.add(rb)

        for b in branches:
            name = b['name']
            if name not in added_recent:
                display = name + (" (默认)" if b.get('default') else "")
                self.branch_combo.addItem(display, name)
        
        self.project_combo.setEnabled(True)
        self.branch_combo.setEnabled(True)
        
        # 在提交者查询完成前，禁用这些控件
        self.author_combo.setEnabled(False)
        self.keyword_input.setEnabled(False)
        self.start_date.setEnabled(False)
        self.end_date.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.query_btn.setEnabled(False)
        
        # 加载提交者列表
        self.load_authors()
    
    def on_branch_error(self, error):
        """分支加载失败"""
        self.show_error(f"获取分支失败: {error}")
        self.project_combo.setEnabled(True)
    
    def load_authors(self):
        """加载提交者列表"""
        branch = self.branch_combo.currentData()
        cache_key = (self.current_project or '', branch or '')
        cached_authors = self._cache_get_authors(cache_key)
        if cached_authors is not None:
            self.on_authors_loaded(cached_authors)
            return

        self.show_progress("正在获取提交者列表...")
        
        thread = GitLabWorkerThread(self.get_authors)
        thread.finished_signal.connect(self.on_authors_loaded)
        thread.error_signal.connect(self.on_authors_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("authors", thread)
        thread.start()
    
    def get_authors(self):
        """获取项目的所有提交者"""
        branch = self.branch_combo.currentData()
        commits = self._get_base_commits(self.current_project, branch, "2000-01-01", None)
        
        authors = set()
        for c in commits:
            author = c.get('author_name', '')
            if author:
                authors.add(author)

        author_list = sorted(list(authors))
        self._cache_set_authors((self.current_project or '', branch or ''), author_list)
        return author_list
    
    def on_authors_loaded(self, authors):
        """提交者列表加载完成"""
        self.author_combo.clear()
        
        for author in authors:
            self.author_combo.addItem(author, author)
        
        self.author_combo.setCurrentIndex(-1)

        self._set_combo_visual_state(self.author_combo, active=True)
        self._set_combo_placeholder(self.author_combo, "全部提交者")
        
        # 提交者查询完成后，启用所有控件
        self.author_combo.setEnabled(True)
        self.keyword_input.setEnabled(True)
        self.start_date.setEnabled(True)
        self.end_date.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.query_btn.setEnabled(True)
        
        self.show_success(f"获取到 {len(authors)} 个提交者")
    
    def on_authors_error(self, error):
        """提交者加载失败"""
        self.show_warning(f"获取提交者失败: {error}")
        self.author_combo.clear()
        self.author_combo.setCurrentIndex(-1)

        self._set_combo_visual_state(self.author_combo, active=True)
        self._set_combo_placeholder(self.author_combo, "全部提交者")
        
        # 即使失败也启用所有控件
        self.author_combo.setEnabled(True)
        self.keyword_input.setEnabled(True)
        self.start_date.setEnabled(True)
        self.end_date.setEnabled(True)
        self.export_btn.setEnabled(True)
        self.query_btn.setEnabled(True)
    
    def on_browse(self):
        """选择保存目录"""
        current_path = self.path_input.text().strip()
        if not current_path:
            current_path = os.path.expanduser("~")
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            current_path
        )
        
        if folder:
            self.path_input.setText(folder)
            self.save_path = folder
            self.save_config()
            self.show_success(f"保存路径已设置")

    def _get_query_context(self, require_save_dir=False):
        """获取当前查询上下文"""
        project_path = self.project_combo.currentData()
        if not project_path:
            project_path = self.project_combo.currentText().replace("★ ", "").strip()

        branch_name = self.branch_combo.currentData()
        if not branch_name:
            branch_name = self.branch_combo.currentText().replace("★ ", "").replace(" (默认)", "").strip()

        author_filter = self.author_combo.currentData() if self.author_combo.currentIndex() >= 0 else ""
        keyword = self.keyword_input.text().strip()
        since_date = self.start_date.date().toString("yyyy-MM-dd")
        until_date = self.end_date.date().toString("yyyy-MM-dd")
        save_dir = self.path_input.text().strip()

        if not self.is_connected or not self.api:
            self.show_warning("请先连接服务器")
            return None

        if not project_path:
            self.show_warning("请选择项目")
            return None

        if not branch_name:
            self.show_warning("请选择分支")
            return None

        if self.start_date.date() > self.end_date.date():
            self.show_warning("开始时间不能晚于结束时间")
            return None

        if require_save_dir and not save_dir:
            self.show_warning("请先设置保存路径")
            return None

        return {
            'project_path': project_path,
            'branch_name': branch_name,
            'author_filter': author_filter,
            'keyword': keyword,
            'since_date': since_date,
            'until_date': until_date,
            'save_dir': save_dir
        }

    def _split_keywords(self, keyword_text):
        """拆分关键词"""
        return [item.strip().lower() for item in keyword_text.replace('；', ';').split(';') if item.strip()]

    @staticmethod
    def _clone_commit_list(commits):
        """复制提交列表，避免缓存对象被外部修改"""
        return [dict(commit) for commit in commits]

    def _cache_get_commits(self, cache, key):
        """获取提交缓存并刷新顺序"""
        value = cache.get(key)
        if value is None:
            return None
        cache.move_to_end(key)
        return self._clone_commit_list(value)

    def _cache_set_commits(self, cache, key, commits, limit=8):
        """写入提交缓存并限制大小"""
        cache[key] = self._clone_commit_list(commits)
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)

    def _cache_get_authors(self, key):
        """获取作者缓存并刷新顺序"""
        value = self.authors_cache.get(key)
        if value is None:
            return None
        self.authors_cache.move_to_end(key)
        return list(value)

    def _cache_set_authors(self, key, authors, limit=12):
        """写入作者缓存并限制大小"""
        self.authors_cache[key] = list(authors)
        self.authors_cache.move_to_end(key)
        while len(self.authors_cache) > limit:
            self.authors_cache.popitem(last=False)

    def _get_base_commit_key(self, project_path, branch_name, since_date, until_date):
        """基础提交缓存键"""
        return (project_path, branch_name or '', since_date, until_date or '')

    def _get_hydrated_commit_key(self, project_path, branch_name, since_date, until_date, author_filter):
        """带文件变化的提交缓存键"""
        return (project_path, branch_name or '', since_date, until_date or '', author_filter or '')

    def _get_base_commits(self, project_path, branch_name, since_date, until_date):
        """获取基础提交列表，命中时直接走缓存"""
        cache_key = self._get_base_commit_key(project_path, branch_name, since_date, until_date)
        cached = self._cache_get_commits(self.base_commits_cache, cache_key)
        if cached is not None:
            return cached

        commits = self.api.get_commits(project_path, since_date, until_date, branch_name)
        self._cache_set_commits(self.base_commits_cache, cache_key, commits)
        return self._clone_commit_list(commits)

    def _fill_commit_changes(self, project_path, commits):
        """补充提交涉及的文件变化"""
        for commit in commits:
            if commit.get('files_changed'):
                continue
            try:
                diff = self.api.get_commit_diff(project_path, commit['id'])
                files = []

                for item in diff:
                    if item.get('new_file'):
                        files.append(f"[新增] {item['new_path']}")
                    elif item.get('deleted_file'):
                        files.append(f"[删除] {item['old_path']}")
                    elif item.get('renamed_file'):
                        files.append(f"[重命名] {item['old_path']} -> {item['new_path']}")
                    else:
                        files.append(f"[修改] {item['new_path']}")

                commit['files_changed'] = '\n'.join(files) if files else '(无文件变化)'
            except Exception:
                commit['files_changed'] = '(获取失败)'

        return commits

    def _filter_commits_by_keywords(self, commits, keyword_text):
        """根据关键词筛选提交记录"""
        keywords = self._split_keywords(keyword_text)
        if not keywords:
            return commits

        filtered = []
        for commit in commits:
            searchable_text = '\n'.join([
                commit.get('title', ''),
                commit.get('message', ''),
                commit.get('author_name', ''),
                commit.get('files_changed', '')
            ]).lower()
            if all(keyword in searchable_text for keyword in keywords):
                filtered.append(commit)
        return filtered

    def _collect_commits(self, project_path, branch_name, since_date, until_date, author_filter="", keyword=""):
        """获取并筛选提交记录"""
        commits = self._get_base_commits(project_path, branch_name, since_date, until_date)
        if not commits:
            return []

        hydrated_key = self._get_hydrated_commit_key(
            project_path, branch_name, since_date, until_date, author_filter
        )
        hydrated_commits = self._cache_get_commits(self.hydrated_commits_cache, hydrated_key)
        if hydrated_commits is None:
            if author_filter:
                commits = [commit for commit in commits if commit.get('author_name') == author_filter]
            if not commits:
                self._cache_set_commits(self.hydrated_commits_cache, hydrated_key, [])
                return []

            self._fill_commit_changes(project_path, commits)
            self._cache_set_commits(self.hydrated_commits_cache, hydrated_key, commits)
            hydrated_commits = self._clone_commit_list(commits)

        commits = hydrated_commits
        commits = self._filter_commits_by_keywords(commits, keyword)
        return commits

    def _format_commit_date(self, date_text):
        """格式化提交时间"""
        if not date_text:
            return ""
        try:
            dt = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return date_text.replace("T", " ").replace("Z", "")

    def _format_commit_records(self, commits):
        """格式化提交记录文本"""
        lines = []
        for index, commit in enumerate(commits, 1):
            commit_id = commit.get('id', '') or commit.get('short_id', '')
            title = (commit.get('title') or '').strip() or '(无标题)'
            message = (commit.get('message') or '').strip() or '(无提交说明)'
            files_changed = commit.get('files_changed', '(无文件变化)')

            lines.append("=" * 80)
            lines.append(f"{index}. {title}")
            lines.append(f"提交者: {commit.get('author_name', '')}")
            lines.append(f"提交时间: {self._format_commit_date(commit.get('committed_date', ''))}")
            lines.append(f"Commit: {commit_id}")
            lines.append("提交说明:")
            lines.extend(message.splitlines())
            lines.append("文件变化:")
            lines.extend(files_changed.splitlines())
            lines.append("")

        return "\n".join(lines).strip()

    def _show_query_result_area(self):
        """显示查询结果区域"""
        self._update_result_area_height()

    def on_query(self):
        """查询日志并展示文本结果"""
        context = self._get_query_context()
        if not context:
            return

        self.add_recent_project(context['project_path'])
        self.add_recent_branch(context['project_path'], context['branch_name'])
        self.save_config()

        self._show_query_result_area()
        self.result_text.clear()
        self.result_text.setExtraSelections([])
        self.last_search_keyword = ""
        self.show_progress("正在查询 Git 提交记录...")
        self.main_buttons.disable()
        self.query_btn.setText("查询中...")

        thread = GitLabWorkerThread(
            self.do_query,
            context['project_path'],
            context['branch_name'],
            context['since_date'],
            context['until_date'],
            context['keyword'],
            context['author_filter']
        )
        thread.finished_signal.connect(self.on_query_finished)
        thread.error_signal.connect(self.on_query_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("query", thread)
        thread.start()

    def do_query(self, project_path, branch_name, since_date, until_date, keyword, author_filter):
        """执行查询操作"""
        commits = self._collect_commits(
            project_path, branch_name, since_date, until_date, author_filter, keyword
        )
        if not commits:
            return None

        return {
            'count': len(commits),
            'content': self._format_commit_records(commits)
        }

    def on_query_finished(self, result):
        """查询完成"""
        self.main_buttons.enable()

        if result is None:
            self.result_text.setPlainText("")
            self.show_warning("没有找到符合条件的提交记录")
            return

        self._show_query_result_area()
        self.result_text.setPlainText(result['content'])
        self.last_search_keyword = ""
        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.result_text.setTextCursor(cursor)
        self.update_search_highlights()
        self._update_result_area_height()
        self.show_success(f"查询完成! 共 {result['count']} 条记录")

    def on_query_error(self, error):
        """查询失败"""
        self.main_buttons.enable()
        self.show_error(f"查询失败: {error}")

    def show_search_bar(self):
        """显示结果搜索栏"""
        self.search_card.setVisible(True)
        self.search_bar.setVisible(True)
        self._update_result_area_height()
        self.search_input.setFocus(Qt.ShortcutFocusReason)
        self.search_input.selectAll()

    def hide_search_bar(self):
        """隐藏结果搜索栏"""
        self.search_bar.setVisible(False)
        self.search_card.setVisible(False)
        self.search_input.clear()
        self.last_search_keyword = ""
        self.result_text.setExtraSelections([])
        self._update_result_area_height()
        self.result_text.setFocus(Qt.ShortcutFocusReason)

    def _find_in_result(self, backward=False):
        """在查询结果中查找关键字"""
        keyword = self.search_input.text().strip()
        if not keyword:
            self.show_warning("请输入搜索关键字")
            return False

        if keyword != self.last_search_keyword:
            self.last_search_keyword = keyword
            cursor = self.result_text.textCursor()
            cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
            self.result_text.setTextCursor(cursor)

        flags = QTextDocument.FindBackward if backward else QTextDocument.FindFlags()
        found = self.result_text.find(keyword, flags)
        if found:
            self.update_search_highlights()
            return True

        cursor = self.result_text.textCursor()
        cursor.movePosition(QTextCursor.End if backward else QTextCursor.Start)
        self.result_text.setTextCursor(cursor)
        found = self.result_text.find(keyword, flags)
        if not found:
            self.show_info(f"未找到：{keyword}")
        self.update_search_highlights()
        return found

    def find_next_in_result(self):
        """查找下一条"""
        self._find_in_result(backward=False)

    def find_previous_in_result(self):
        """查找上一条"""
        self._find_in_result(backward=True)

    def on_export(self):
        """导出日志"""
        context = self._get_query_context(require_save_dir=True)
        if not context:
            return
        
        # 生成文件名
        filename = (
            f"gitlog_{context['project_path'].replace('/', '_')}_{context['branch_name']}_"
            f"{context['since_date']}_to_{context['until_date']}.xlsx"
        )
        save_path = os.path.join(context['save_dir'], filename)
        
        # 如果文件已存在，添加序号
        counter = 1
        base_path = save_path[:-5]
        while os.path.exists(save_path):
            save_path = f"{base_path}_{counter}.xlsx"
            counter += 1
        
        # 保存最近使用记录
        self.add_recent_project(context['project_path'])
        self.add_recent_branch(context['project_path'], context['branch_name'])
        self.save_config()
        
        self.show_progress("开始导出日志...")
        self.main_buttons.disable()
        self.export_btn.setText("导出中...")
        
        thread = GitLabWorkerThread(
            self.do_export,
            context['project_path'],
            context['branch_name'],
            context['since_date'],
            context['until_date'],
            context['keyword'],
            context['author_filter'],
            save_path
        )
        thread.finished_signal.connect(self.on_export_finished)
        thread.error_signal.connect(self.on_export_error)
        thread.progress_signal.connect(lambda msg: self.show_progress(msg))
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("export", thread)
        thread.start()
    
    def do_export(self, project_path, branch_name, since_date, until_date, keyword, author_filter, save_path):
        """执行导出操作"""
        commits = self._collect_commits(
            project_path, branch_name, since_date, until_date, author_filter, keyword
        )
        if not commits:
            return None

        # 创建 Excel 文件
        create_gitlab_xlsx(commits, save_path, keyword)
        
        return {'count': len(commits), 'file': save_path}
    
    def on_export_finished(self, result):
        """导出完成"""
        self.main_buttons.enable()
        
        if result is None:
            self.show_warning("没有找到符合条件的提交记录")
        else:
            filename = os.path.basename(result['file'])
            self.show_success(f"导出完成! 共 {result['count']} 条记录，文件: {filename}")
    
    def on_export_error(self, error):
        """导出失败"""
        self.main_buttons.enable()
        self.show_error(f"导出失败: {error}")
    
    def add_recent_project(self, project_path):
        """添加最近使用的项目"""
        if project_path in self.recent_projects:
            self.recent_projects.remove(project_path)
        self.recent_projects.insert(0, project_path)
        self.recent_projects = self.recent_projects[:6]
    
    def add_recent_branch(self, project_path, branch_name):
        """添加最近使用的分支"""
        if project_path not in self.recent_branches:
            self.recent_branches[project_path] = []
        
        branches = self.recent_branches[project_path]
        if branch_name in branches:
            branches.remove(branch_name)
        branches.insert(0, branch_name)
        self.recent_branches[project_path] = branches[:6]
    
    def on_page_show(self):
        """页面显示时"""
        self.show_info("GIT日志页面")
    
    def load_config(self):
        """加载配置"""
        reg_key = None
        try:
            # 从注册表加载 GitLab 配置
            import winreg
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\TPQueryTool\GitLab",
                0,
                winreg.KEY_READ
            )
            
            try:
                self.gitlab_server, _ = winreg.QueryValueEx(reg_key, "server")
                self.server_input.setText(self.gitlab_server)
            except (WindowsError, FileNotFoundError):
                pass
            
            try:
                import base64
                token_encoded, _ = winreg.QueryValueEx(reg_key, "token")
                self.gitlab_token = base64.b64decode(token_encoded.encode()).decode()
                self.token_input.setText(self.gitlab_token)
            except (WindowsError, FileNotFoundError, ValueError, UnicodeDecodeError):
                pass
            
            try:
                self.save_path, _ = winreg.QueryValueEx(reg_key, "save_path")
                self.path_input.setText(self.save_path)
            except (WindowsError, FileNotFoundError):
                pass
            
            try:
                import json
                recent_projects_str, _ = winreg.QueryValueEx(reg_key, "recent_projects")
                self.recent_projects = json.loads(recent_projects_str) if recent_projects_str else []
            except (WindowsError, FileNotFoundError, json.JSONDecodeError):
                pass
            
            try:
                import json
                recent_branches_str, _ = winreg.QueryValueEx(reg_key, "recent_branches")
                self.recent_branches = json.loads(recent_branches_str) if recent_branches_str else {}
            except (WindowsError, FileNotFoundError, json.JSONDecodeError):
                pass
            
        except (WindowsError, FileNotFoundError, OSError):
            pass
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.debug(f"关闭注册表键失败: {e}")
    
    def save_config(self):
        """保存配置"""
        reg_key = None
        try:
            import winreg
            import base64
            import json
            from query_tool.utils.logger import logger
            
            reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\TPQueryTool\GitLab")
            
            # 保存服务器地址
            server = self.server_input.text().strip()
            if server:
                winreg.SetValueEx(reg_key, "server", 0, winreg.REG_SZ, server)
            
            # 保存 Token（加密）
            token = self.token_input.text().strip()
            if token:
                token_encoded = base64.b64encode(token.encode()).decode()
                winreg.SetValueEx(reg_key, "token", 0, winreg.REG_SZ, token_encoded)
            
            # 保存路径
            if self.save_path:
                winreg.SetValueEx(reg_key, "save_path", 0, winreg.REG_SZ, self.save_path)
            
            # 保存最近项目
            recent_projects_str = json.dumps(self.recent_projects[:6])
            winreg.SetValueEx(reg_key, "recent_projects", 0, winreg.REG_SZ, recent_projects_str)
            
            # 保存最近分支
            recent_branches_str = json.dumps(self.recent_branches)
            winreg.SetValueEx(reg_key, "recent_branches", 0, winreg.REG_SZ, recent_branches_str)
            
        except (WindowsError, OSError) as e:
            from query_tool.utils.logger import logger
            logger.error(f"保存配置失败: {e}")
        finally:
            if reg_key:
                try:
                    winreg.CloseKey(reg_key)
                except Exception as e:
                    from query_tool.utils.logger import logger
                    logger.debug(f"关闭注册表键失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        self.thread_mgr.stop_all()

    def fast_cleanup(self):
        """更新重启时快速结束后台线程。"""
        self.thread_mgr.stop_all(wait_ms=300, force=True)

    def refresh_theme(self):
        """主题切换时刷新回退模式的输入样式。"""
        for label in self._card_title_labels:
            self._apply_card_title_style(label)
        for card in self._cards:
            self._apply_card_style(card)
        self._lock_static_group_heights()
        if hasattr(self, 'project_combo'):
            self._set_combo_visual_state(self.project_combo, active=self.is_connected)
        if hasattr(self, 'author_combo'):
            self._set_combo_visual_state(self.author_combo, active=self.is_connected)
        if hasattr(self, 'branch_combo'):
            self._set_combo_visual_state(self.branch_combo, active=self.is_connected)
        if hasattr(self, 'result_text') and not QFLUENT_WIDGETS_AVAILABLE:
            self.result_text.setStyleSheet(StyleManager.get_PLAINTEXT_EDIT_TABLE())
        self._update_result_area_height()

