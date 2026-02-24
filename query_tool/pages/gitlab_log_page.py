"""
GitLab 日志导出页面
提供 GitLab 提交日志查询和导出功能
"""
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QDateEdit, QGroupBox, QScrollArea, QWidget,
    QFileDialog, QFrame
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import ButtonManager, ThreadManager, config_manager
from query_tool.utils.logger import logger
from query_tool.utils.gitlab_api import GitLabAPI
from query_tool.utils.excel_helper import create_gitlab_xlsx
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


@register_page("GIT", order=3, icon=":/icons/system/git.png")
class GitLabLogPage(BasePage):
    """GitLab 日志导出页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "GIT"
        
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
        
        self.init_ui()
        self.load_config()
    
    def init_ui(self):
        """初始化UI"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 使用滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        
        # 1. 服务器连接区
        self.create_connection_area(content_layout)
        
        # 2. 查询条件区
        self.create_query_area(content_layout)
        
        # 3. 时间范围和导出区
        self.create_export_area(content_layout)
        
        # 添加弹性空间
        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        
        # 创建按钮组
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(
            self.connect_btn, self.browse_btn, self.export_btn
        )
        
        # 初始状态
        self.set_controls_enabled(False)
    
    def create_connection_area(self, parent_layout):
        """创建服务器连接区域"""
        group = QGroupBox("服务器连接")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # 服务器地址
        server_layout = QHBoxLayout()
        server_label = QLabel("服务器:")
        server_label.setFixedWidth(70)
        server_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("https://gitlab.example.com")
        self.server_input.setMinimumHeight(28)
        server_layout.addWidget(server_label)
        server_layout.addWidget(self.server_input, 1)
        layout.addLayout(server_layout)
        
        # Token
        token_layout = QHBoxLayout()
        token_label = QLabel("Token:")
        token_label.setFixedWidth(70)
        token_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("请输入 GitLab Token")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setMinimumHeight(28)
        
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/connect.png"))
        self.connect_btn.setIconSize(QSize(16, 16))
        self.connect_btn.setFixedSize(80, 28)
        self.connect_btn.clicked.connect(self.on_connect)
        
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.token_input, 1)
        token_layout.addWidget(self.connect_btn)
        layout.addLayout(token_layout)
        
        parent_layout.addWidget(group)
    
    def create_query_area(self, parent_layout):
        """创建查询条件区域"""
        group = QGroupBox("查询条件")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # 项目
        project_layout = QHBoxLayout()
        project_label = QLabel("项目:")
        project_label.setFixedWidth(70)
        project_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(28)
        self.project_combo.setEditable(True)
        self.project_combo.setInsertPolicy(QComboBox.NoInsert)
        self.project_combo.setFocusPolicy(Qt.StrongFocus)  # 禁用滚轮改变值
        # 初始不显示占位文字
        self.project_combo.lineEdit().setPlaceholderText("")
        
        # 设置项目下拉框 lineEdit 初始样式（透明背景）
        project_line_edit = self.project_combo.lineEdit()
        if project_line_edit:
            project_line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: transparent;
                    color: #606060;
                    border: none;
                    padding: 4px;
                }
            """)
        
        # 禁用滚轮事件
        self.project_combo.wheelEvent = lambda event: event.ignore()
        
        self.project_combo.activated.connect(self.on_project_selected)
        project_layout.addWidget(project_label)
        project_layout.addWidget(self.project_combo, 1)
        layout.addLayout(project_layout)
        
        # 分支
        branch_layout = QHBoxLayout()
        branch_label = QLabel("分支:")
        branch_label.setFixedWidth(70)
        branch_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumHeight(28)
        self.branch_combo.setFocusPolicy(Qt.StrongFocus)  # 禁用滚轮改变值
        
        # 禁用滚轮事件
        self.branch_combo.wheelEvent = lambda event: event.ignore()
        
        branch_layout.addWidget(branch_label)
        branch_layout.addWidget(self.branch_combo, 1)
        layout.addLayout(branch_layout)
        
        # 提交者
        author_layout = QHBoxLayout()
        author_label = QLabel("提交者:")
        author_label.setFixedWidth(70)
        author_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.author_combo = QComboBox()
        self.author_combo.setMinimumHeight(28)
        self.author_combo.setEditable(True)
        self.author_combo.setInsertPolicy(QComboBox.NoInsert)
        self.author_combo.setFocusPolicy(Qt.StrongFocus)  # 禁用滚轮改变值
        # 初始不显示占位文字
        self.author_combo.lineEdit().setPlaceholderText("")
        
        # 设置提交者下拉框 lineEdit 初始样式（透明背景）
        author_line_edit = self.author_combo.lineEdit()
        if author_line_edit:
            author_line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: transparent;
                    color: #606060;
                    border: none;
                    padding: 4px;
                }
            """)
        
        # 禁用滚轮事件
        self.author_combo.wheelEvent = lambda event: event.ignore()
        
        author_layout.addWidget(author_label)
        author_layout.addWidget(self.author_combo, 1)
        layout.addLayout(author_layout)
        
        # 关键词
        keyword_layout = QHBoxLayout()
        keyword_label = QLabel("关键词:")
        keyword_label.setFixedWidth(70)
        keyword_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("多个关键词用分号隔开，导出后高亮")
        self.keyword_input.setMinimumHeight(28)
        keyword_layout.addWidget(keyword_label)
        keyword_layout.addWidget(self.keyword_input, 1)
        layout.addLayout(keyword_layout)
        
        parent_layout.addWidget(group)
    
    def create_export_area(self, parent_layout):
        """创建时间范围和导出区域"""
        group = QGroupBox("时间范围与导出")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # 时间范围（水平排列）
        time_layout = QHBoxLayout()
        
        # 开始时间
        start_label = QLabel("开始时间:")
        start_label.setFixedWidth(70)
        start_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setMinimumHeight(28)
        time_layout.addWidget(start_label)
        time_layout.addWidget(self.start_date, 1)
        
        # 添加间距
        time_layout.addSpacing(20)
        
        # 结束时间
        end_label = QLabel("结束时间:")
        end_label.setFixedWidth(70)
        end_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setMinimumHeight(28)
        time_layout.addWidget(end_label)
        time_layout.addWidget(self.end_date, 1)
        
        layout.addLayout(time_layout)
        
        # 保存路径
        path_layout = QHBoxLayout()
        path_label = QLabel("保存路径:")
        path_label.setFixedWidth(70)
        path_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.path_input = ClickableLineEdit()
        self.path_input.setPlaceholderText("点击浏览选择保存目录（双击可打开目录）")
        self.path_input.setReadOnly(True)
        self.path_input.setFocusPolicy(Qt.NoFocus)
        self.path_input.setMinimumHeight(28)
        
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setIcon(QIcon(":/icons/gitlab/browser.png"))
        self.browse_btn.setIconSize(QSize(16, 16))
        self.browse_btn.setFixedSize(80, 28)
        self.browse_btn.clicked.connect(self.on_browse)
        
        self.export_btn = QPushButton("导出")
        self.export_btn.setIcon(QIcon(":/icons/gitlab/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(80, 28)
        self.export_btn.clicked.connect(self.on_export)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input, 1)
        path_layout.addWidget(self.browse_btn)
        path_layout.addWidget(self.export_btn)
        layout.addLayout(path_layout)
        
        parent_layout.addWidget(group)

    
    def set_controls_enabled(self, enabled):
        """设置控件启用状态"""
        self.project_combo.setEnabled(enabled)
        self.branch_combo.setEnabled(enabled)
        self.author_combo.setEnabled(enabled)
        self.keyword_input.setEnabled(enabled)
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)
        self.export_btn.setEnabled(enabled)
    
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
        
        # 更新按钮
        self.connect_btn.setText("连接")
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/connect.png"))
        
        # 清空并禁用控件
        self.project_combo.clear()
        self.branch_combo.clear()
        self.author_combo.clear()
        
        # 清空占位文字
        self.project_combo.lineEdit().setPlaceholderText("")
        self.author_combo.lineEdit().setPlaceholderText("")
        
        # 移除背景色（设置为透明/禁用样式）
        self.project_combo.lineEdit().setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #606060;
                border: none;
                padding: 4px;
            }
        """)
        
        # 分支下拉框也需要设置透明背景
        # 如果分支下拉框是可编辑的，需要设置 lineEdit 样式
        if self.branch_combo.lineEdit():
            self.branch_combo.lineEdit().setStyleSheet("""
                QLineEdit {
                    background-color: transparent;
                    color: #606060;
                    border: none;
                    padding: 4px;
                }
            """)
        
        self.author_combo.lineEdit().setStyleSheet("""
            QLineEdit {
                background-color: transparent;
                color: #606060;
                border: none;
                padding: 4px;
            }
        """)
        
        self.set_controls_enabled(False)
        
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
        self.connect_btn.setIcon(QIcon(":/icons/gitlab/disconnect.png"))
        self.connect_btn.setEnabled(True)
        
        # 恢复项目下拉框的样式和占位文字
        self.project_combo.lineEdit().setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: none;
                padding: 4px;
                selection-background-color: #505050;
            }
        """)
        self.project_combo.lineEdit().setPlaceholderText("请选择或输入项目名...")
        
        # 填充项目列表
        self.project_combo.clear()
        
        # 添加最近使用的项目
        added_recent = []
        for rp in self.recent_projects:
            if any(p['path_with_namespace'] == rp for p in projects):
                self.project_combo.addItem(f"★ {rp}", rp)
                added_recent.append(rp)
        
        # 添加分隔符
        if added_recent:
            self.project_combo.insertSeparator(len(added_recent))
        
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
        
        # 设置分支下拉框可搜索
        self.branch_combo.setEditable(True)
        self.branch_combo.setInsertPolicy(QComboBox.NoInsert)
        
        # 设置 lineEdit 的样式（恢复正常背景色）
        line_edit = self.branch_combo.lineEdit()
        if line_edit:
            line_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #404040;
                    color: #e0e0e0;
                    border: none;
                    padding: 4px;
                    selection-background-color: #505050;
                }
            """)
        
        self.branch_combo.clear()
        
        # 默认分支放前面
        default_branch = next((b for b in branches if b.get('default')), None)
        if default_branch:
            branches.remove(default_branch)
            branches.insert(0, default_branch)
        
        # 获取最近使用的分支
        recent_branches = self.recent_branches.get(self.current_project, [])
        added_recent = []
        
        for rb in recent_branches:
            if any(b['name'] == rb for b in branches):
                self.branch_combo.addItem(f"★ {rb}", rb)
                added_recent.append(rb)
        
        if added_recent:
            self.branch_combo.insertSeparator(len(added_recent))
        
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
        
        # 加载提交者列表
        self.load_authors()
    
    def on_branch_error(self, error):
        """分支加载失败"""
        self.show_error(f"获取分支失败: {error}")
        self.project_combo.setEnabled(True)
    
    def load_authors(self):
        """加载提交者列表"""
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
        commits = self.api.get_commits(self.current_project, "2000-01-01", None, branch)
        
        authors = set()
        for c in commits:
            author = c.get('author_name', '')
            if author:
                authors.add(author)
        
        return sorted(list(authors))
    
    def on_authors_loaded(self, authors):
        """提交者列表加载完成"""
        self.author_combo.clear()
        
        for author in authors:
            self.author_combo.addItem(author, author)
        
        self.author_combo.setCurrentIndex(-1)
        
        # 恢复提交者下拉框的样式和占位文字
        self.author_combo.lineEdit().setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: none;
                padding: 4px;
                selection-background-color: #505050;
            }
        """)
        self.author_combo.lineEdit().setPlaceholderText("全部提交者")
        
        # 提交者查询完成后，启用所有控件
        self.author_combo.setEnabled(True)
        self.keyword_input.setEnabled(True)
        self.start_date.setEnabled(True)
        self.end_date.setEnabled(True)
        self.export_btn.setEnabled(True)
        
        self.show_success(f"获取到 {len(authors)} 个提交者")
    
    def on_authors_error(self, error):
        """提交者加载失败"""
        self.show_warning(f"获取提交者失败: {error}")
        self.author_combo.clear()
        self.author_combo.setCurrentIndex(-1)
        
        # 即使失败也恢复样式和占位文字
        self.author_combo.lineEdit().setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: none;
                padding: 4px;
                selection-background-color: #505050;
            }
        """)
        self.author_combo.lineEdit().setPlaceholderText("全部提交者")
        
        # 即使失败也启用所有控件
        self.author_combo.setEnabled(True)
        self.keyword_input.setEnabled(True)
        self.start_date.setEnabled(True)
        self.end_date.setEnabled(True)
        self.export_btn.setEnabled(True)
    
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
    
    def on_export(self):
        """导出日志"""
        project_path = self.project_combo.currentData()
        if not project_path:
            project_path = self.project_combo.currentText().replace("★ ", "")
        
        branch_name = self.branch_combo.currentData()
        author_filter = self.author_combo.currentData() if self.author_combo.currentIndex() >= 0 else ""
        keyword = self.keyword_input.text().strip()
        since_date = self.start_date.date().toString("yyyy-MM-dd")
        until_date = self.end_date.date().toString("yyyy-MM-dd")
        save_dir = self.path_input.text().strip()
        
        if not branch_name:
            self.show_warning("请选择分支")
            return
        
        if not save_dir:
            self.show_warning("请先设置保存路径")
            return
        
        # 生成文件名
        filename = f"gitlog_{project_path.replace('/', '_')}_{branch_name}_{since_date}_to_{until_date}.xlsx"
        save_path = os.path.join(save_dir, filename)
        
        # 如果文件已存在，添加序号
        counter = 1
        base_path = save_path[:-5]
        while os.path.exists(save_path):
            save_path = f"{base_path}_{counter}.xlsx"
            counter += 1
        
        # 保存最近使用记录
        self.add_recent_project(project_path)
        self.add_recent_branch(project_path, branch_name)
        self.save_config()
        
        self.show_progress("开始导出日志...")
        self.main_buttons.disable()
        self.export_btn.setText("导出中...")
        
        thread = GitLabWorkerThread(
            self.do_export, project_path, branch_name, since_date, 
            until_date, keyword, author_filter, save_path
        )
        thread.finished_signal.connect(self.on_export_finished)
        thread.error_signal.connect(self.on_export_error)
        thread.progress_signal.connect(lambda msg: self.show_progress(msg))
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("export", thread)
        thread.start()
    
    def do_export(self, project_path, branch_name, since_date, until_date, keyword, author_filter, save_path):
        """执行导出操作"""
        # 获取提交记录
        commits = self.api.get_commits(project_path, since_date, until_date, branch_name)
        
        if not commits:
            return None
        
        # 按提交者筛选
        if author_filter:
            commits = [c for c in commits if c.get('author_name') == author_filter]
        
        if not commits:
            return None
        
        # 获取文件变化
        for idx, commit in enumerate(commits, 1):
            try:
                diff = self.api.get_commit_diff(project_path, commit['id'])
                files = []
                
                for d in diff:
                    if d.get('new_file'):
                        files.append(f"[新增] {d['new_path']}")
                    elif d.get('deleted_file'):
                        files.append(f"[删除] {d['old_path']}")
                    elif d.get('renamed_file'):
                        files.append(f"[重命名] {d['old_path']} -> {d['new_path']}")
                    else:
                        files.append(f"[修改] {d['new_path']}")
                
                commit['files_changed'] = '\n'.join(files) if files else '(无文件变化)'
            except Exception:
                commit['files_changed'] = '(获取失败)'
        
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
