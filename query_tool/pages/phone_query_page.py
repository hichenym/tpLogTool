"""
账号设备查询页面
根据手机号查询用户绑定的设备
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QCompleter, QMessageBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import ThreadManager, get_account_config
from query_tool.utils.workers import PhoneQueryThread
from query_tool.widgets import PlainTextEdit, show_question_box


@register_page("账号", order=2, icon=":/icons/system/user.png")
class PhoneQueryPage(BasePage):
    """账号设备查询页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "账号"
        
        # 管理器
        self.thread_mgr = ThreadManager()
        
        # 数据
        self.phone_query_results = []
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # 查询与筛选分组
        query_group = self.create_query_group()
        layout.addWidget(query_group)
        
        # 查询结果分组
        result_group = self.create_result_group()
        layout.addWidget(result_group)
    
    def create_query_group(self):
        """创建查询与筛选分组"""
        from PyQt5.QtWidgets import QGroupBox, QLineEdit, QGridLayout
        
        group = QGroupBox("查询与筛选")
        group_layout = QGridLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(10)
        
        # 设置列宽比例：第一列(账号/型号) : 第二列(SN/版本) : 第三列(查询/数量) = 4 : 7 : 1
        group_layout.setColumnStretch(0, 4)
        group_layout.setColumnStretch(1, 9)
        group_layout.setColumnStretch(2, 1)
        
        # ===== 第一行：账号输入 + SN筛选 + 查询按钮 =====
        phone_label = QLabel("账号:")
        phone_label.setFixedWidth(35)
        phone_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.phone_input = QComboBox()
        self.phone_input.setEditable(True)
        self.phone_input.setInsertPolicy(QComboBox.NoInsert)
        self.phone_input.setFocusPolicy(Qt.StrongFocus)
        self.phone_input.lineEdit().setPlaceholderText("请输入账号...")
        self.phone_input.setFixedHeight(28)
        self.phone_input.wheelEvent = lambda event: event.ignore()
        
        # 第一列：账号
        phone_layout = QHBoxLayout()
        phone_layout.setContentsMargins(0, 0, 0, 0)
        phone_layout.setSpacing(5)
        phone_layout.addWidget(phone_label)
        phone_layout.addWidget(self.phone_input, 1)
        
        # SN筛选
        sn_label = QLabel("SN:")
        sn_label.setFixedWidth(35)
        sn_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.sn_filter_input = QLineEdit()
        self.sn_filter_input.setFixedHeight(28)
        self.sn_filter_input.setPlaceholderText("输入SN筛选...")
        self.sn_filter_input.textChanged.connect(self.on_filter_changed)
        
        sn_layout = QHBoxLayout()
        sn_layout.setContentsMargins(0, 0, 0, 0)
        sn_layout.setSpacing(5)
        sn_layout.addWidget(sn_label)
        sn_layout.addWidget(self.sn_filter_input, 1)
        
        # 第三列：查询按钮
        self.phone_query_btn = QPushButton("查询")
        self.phone_query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.phone_query_btn.setIconSize(QSize(16, 16))
        self.phone_query_btn.setFixedSize(80, 28)
        self.phone_query_btn.clicked.connect(self.on_phone_query)
        
        group_layout.addLayout(phone_layout, 0, 0)
        group_layout.addLayout(sn_layout, 0, 1)
        group_layout.addWidget(self.phone_query_btn, 0, 2)
        
        # ===== 第二行：型号筛选 + 版本筛选 + 数量显示 =====
        model_label = QLabel("型号:")
        model_label.setFixedWidth(35)
        model_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(28)
        self.model_combo.setFocusPolicy(Qt.StrongFocus)
        self.model_combo.addItem("全部")
        self.model_combo.currentIndexChanged.connect(self.on_filter_changed)
        self.model_combo.wheelEvent = lambda event: event.ignore()
        
        model_layout = QHBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(5)
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo, 1)
        
        # 版本筛选
        version_label = QLabel("版本:")
        version_label.setFixedWidth(35)
        version_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.version_combo = QComboBox()
        self.version_combo.setFixedHeight(28)
        self.version_combo.setFocusPolicy(Qt.StrongFocus)
        self.version_combo.setEditable(False)
        self.version_combo.addItem("全部")
        self.version_combo.currentIndexChanged.connect(self.on_filter_changed)
        self.version_combo.wheelEvent = lambda event: event.ignore()
        
        version_layout = QHBoxLayout()
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setSpacing(5)
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.version_combo, 1)
        
        # 数量显示
        self.device_count_label = QLabel("数量: 0")
        self.device_count_label.setFixedSize(80, 28)
        self.device_count_label.setAlignment(Qt.AlignCenter)
        
        group_layout.addLayout(model_layout, 1, 0)
        group_layout.addLayout(version_layout, 1, 1)
        group_layout.addWidget(self.device_count_label, 1, 2)
        
        return group
    
    def create_result_group(self):
        """创建查询结果分组"""
        from PyQt5.QtWidgets import QGroupBox
        
        group = QGroupBox("查询结果")
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(10)
        
        # 结果表格
        self.phone_result_table = QTableWidget()
        self.phone_result_table.setColumnCount(4)
        self.phone_result_table.setHorizontalHeaderLabels(["型号", "设备名", "SN", "版本"])
        self.phone_result_table.setFocusPolicy(Qt.StrongFocus)
        self.phone_result_table.setSelectionMode(QTableWidget.SingleSelection)
        self.phone_result_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.phone_result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.phone_result_table.setShowGrid(True)
        self.phone_result_table.setFrameShape(QTableWidget.NoFrame)
        
        # 应用深色主题样式
        from query_tool.utils import StyleManager
        StyleManager.apply_to_widget(self.phone_result_table, "TABLE")
        
        header = self.phone_result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.phone_result_table.setColumnWidth(0, 150)
        self.phone_result_table.setColumnWidth(1, 200)
        self.phone_result_table.setColumnWidth(2, 150)
        
        self.phone_result_table.cellDoubleClicked.connect(self.on_phone_cell_double_clicked)
        self.phone_result_table.cellClicked.connect(self.on_phone_cell_clicked)
        
        # SN列表文本框
        self.sn_list_text = PlainTextEdit()
        self.sn_list_text.setPlaceholderText("筛选后的SN列表...")
        self.sn_list_text.setReadOnly(True)
        self.sn_list_text.setMinimumWidth(180)
        self.sn_list_text.setMaximumWidth(250)
        
        # 设置背景色与输入框一致
        self.sn_list_text.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
            QTextEdit:focus {
                border: 1px solid #555555;
            }
        """)
        
        group_layout.addWidget(self.phone_result_table, 3)
        group_layout.addWidget(self.sn_list_text, 1)
        
        return group
    
    def on_page_show(self):
        """页面显示时"""
        self.show_info("账号页面")
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 账号查询页面的表格使用Stretch模式，会自动调整
    
    def on_phone_query(self):
        """账号查询按钮点击"""
        phone = self.phone_input.currentText().strip()
        
        if not phone:
            self.show_warning("请输入账号")
            return
        
        # 检查账号密码
        env, username, password = get_account_config()
        if not username or not password:
            reply = show_question_box(
                self, "需要配置账号密码",
                "检测到账号密码未配置，是否现在配置？"
            )
            if reply == QMessageBox.Yes:
                from query_tool.widgets import SettingsDialog
                dialog = SettingsDialog(self)
                dialog.exec_()
            return
        
        # 禁用按钮和筛选控件
        self.phone_query_btn.setEnabled(False)
        self.phone_query_btn.setText("查询中...")
        self.model_combo.setEnabled(False)
        self.version_combo.setEnabled(False)
        self.sn_filter_input.setEnabled(False)
        
        # 清空结果和筛选条件
        self.phone_query_results = []
        self.model_combo.clear()
        self.model_combo.addItem("全部")
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        self.sn_filter_input.clear()
        self.phone_result_table.setRowCount(0)
        
        # 启动查询线程
        phone_query_thread = PhoneQueryThread(phone, env, username, password)
        phone_query_thread.progress.connect(lambda msg: self.show_progress(msg))
        phone_query_thread.error.connect(self.on_phone_query_error)
        phone_query_thread.success.connect(self.on_phone_query_success)
        
        self.thread_mgr.add("phone_query", phone_query_thread)
        phone_query_thread.start()
    
    def on_phone_query_error(self, error_msg):
        """查询出错"""
        self.phone_query_btn.setEnabled(True)
        self.phone_query_btn.setText("查询")
        self.model_combo.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.sn_filter_input.setEnabled(True)
        self.show_error(error_msg)
    
    def on_phone_query_success(self, results, models):
        """查询成功"""
        self.phone_query_results = results
        
        # 添加型号到下拉框
        for model in models:
            self.model_combo.addItem(model)
        
        # 清空SN和版本筛选框
        self.sn_filter_input.clear()
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        
        # 提取所有版本号
        versions = set()
        for device in self.phone_query_results:
            version = device.get("version", "")
            if version and version not in ["", "未知"]:
                versions.add(version)
        
        # 添加版本号到下拉框
        for version in sorted(list(versions)):
            self.version_combo.addItem(version)
        
        self.version_combo.blockSignals(False)
        
        # 显示所有设备
        self.update_phone_result_table()
        
        # 添加手机号到历史
        phone = self.phone_input.currentText().strip()
        self.add_phone_to_history(phone)
        
        # 恢复按钮和筛选控件
        self.phone_query_btn.setEnabled(True)
        self.phone_query_btn.setText("查询")
        self.model_combo.setEnabled(True)
        self.version_combo.setEnabled(True)
        self.sn_filter_input.setEnabled(True)
        
        self.show_success(f"查询完成，共找到 {len(self.phone_query_results)} 台设备")
    
    def on_filter_changed(self):
        """筛选条件变化（型号、SN或版本）"""
        # 如果是型号或SN变化，更新版本下拉框
        sender = self.sender()
        if sender == self.model_combo or sender == self.sn_filter_input:
            self.update_version_combo()
        
        self.update_phone_result_table()
    
    def update_version_combo(self):
        """根据选中的型号和SN筛选更新版本下拉框"""
        selected_model = self.model_combo.currentText()
        sn_filter = self.sn_filter_input.text().strip().lower()
        
        # 获取当前选中的版本
        current_version = self.version_combo.currentText()
        
        # 阻止信号，避免触发筛选
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        
        # 提取对应条件的所有版本号
        versions = set()
        
        # 先按型号筛选
        filtered_devices = self.phone_query_results
        if selected_model != "全部":
            filtered_devices = [d for d in filtered_devices if d["model"] == selected_model]
        
        # 再按SN筛选
        if sn_filter:
            filtered_devices = [d for d in filtered_devices if sn_filter in d["sn"].lower()]
        
        # 提取版本号
        for device in filtered_devices:
            version = device.get("version", "")
            if version and version not in ["", "未知"]:
                versions.add(version)
        
        # 添加版本号到下拉框
        for version in sorted(list(versions)):
            self.version_combo.addItem(version)
        
        # 恢复之前选中的版本（如果存在）
        index = self.version_combo.findText(current_version)
        if index >= 0:
            self.version_combo.setCurrentIndex(index)
        else:
            self.version_combo.setCurrentIndex(0)
        
        self.version_combo.blockSignals(False)
    
    def update_phone_result_table(self):
        """更新结果表格"""
        selected_model = self.model_combo.currentText()
        sn_filter = self.sn_filter_input.text().strip().lower()
        selected_version = self.version_combo.currentText()
        
        # 筛选设备
        filtered_devices = self.phone_query_results
        
        # 按型号筛选
        if selected_model != "全部":
            filtered_devices = [d for d in filtered_devices if d["model"] == selected_model]
        
        # 按SN筛选
        if sn_filter:
            filtered_devices = [d for d in filtered_devices if sn_filter in d["sn"].lower()]
        
        # 按版本筛选
        if selected_version != "全部":
            filtered_devices = [d for d in filtered_devices if d.get("version") == selected_version]
        
        # 更新设备数量
        self.device_count_label.setText(f"数量: {len(filtered_devices)}")
        
        # 更新表格
        self.phone_result_table.setRowCount(len(filtered_devices))
        sn_list = []
        for row, device in enumerate(filtered_devices):
            self.phone_result_table.setItem(row, 0, QTableWidgetItem(device["model"]))
            self.phone_result_table.setItem(row, 1, QTableWidgetItem(device["name"]))
            self.phone_result_table.setItem(row, 2, QTableWidgetItem(device["sn"]))
            self.phone_result_table.setItem(row, 3, QTableWidgetItem(device.get("version", "")))
            sn_list.append(device["sn"])
        
        # 更新SN列表
        self.sn_list_text.setPlainText('\n'.join(sn_list))
    
    def on_phone_cell_double_clicked(self, row, column):
        """双击复制"""
        item = self.phone_result_table.item(row, column)
        if item:
            text = item.text()
            if text:
                from PyQt5.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                
                # 选中当前单元格
                self.phone_result_table.setCurrentCell(row, column)
                
                self.show_success(f"已复制: {text}", 2000)
    
    def on_phone_cell_clicked(self, row, column):
        """单击选中单元格"""
        # 选中当前单元格
        self.phone_result_table.setCurrentCell(row, column)
    
    def add_phone_to_history(self, phone):
        """添加手机号到历史"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        
        if phone in app_config.phone_history:
            app_config.phone_history.remove(phone)
        
        app_config.phone_history.insert(0, phone)
        app_config.phone_history = app_config.phone_history[:5]
        
        self.phone_input.clear()
        self.phone_input.addItems(app_config.phone_history)
        
        config_manager.save_app_config(app_config)
    
    def load_config(self):
        """加载配置"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        if app_config.phone_history:
            self.phone_input.addItems(app_config.phone_history)
            completer = self.phone_input.completer()
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
    
    def cleanup(self):
        """清理资源"""
        self.thread_mgr.stop_all()
