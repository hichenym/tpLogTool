"""
设备状态查询页面
提供设备信息查询、唤醒、导出等功能
"""
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QSplitter, QFrame,
    QFileDialog, QMessageBox, QWidget, QComboBox
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import (
    ButtonManager, MessageManager, ThreadManager, StyleManager, TableHelper,
    get_account_config, DeviceQuery, check_device_online
)
from query_tool.utils.workers import QueryThread, WakeThread
from query_tool.widgets import PlainTextEdit, ClickableLineEdit, show_question_box


class NoWheelComboBox(QComboBox):
    """禁用鼠标滚轮切换的下拉框"""
    def wheelEvent(self, event):
        """禁用鼠标滚轮事件"""
        event.ignore()


@register_page("设备", order=1, icon=":/icons/system/device.png")
class DeviceStatusPage(BasePage):
    """设备状态查询页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "设备"
        
        # 管理器
        self.btn_manager = ButtonManager()
        self.thread_mgr = ThreadManager()
        
        # 线程数设置
        self.thread_count = 40  # 默认线程数改为 40
        self.thread_count_combo = None  # 线程数下拉框
        
        # 数据
        self.query_results = {}
        self.query_input_type = None
        self.query_input_list = []
        self.export_path = ""
        self.total_count = 0
        self.online_count = 0
        self.offline_count = 0
        
        # 版本过滤相关
        self.all_versions = set()
        self.current_version_filter = None
        self.filtered_results = {}  # 存储过滤后的结果
        self.display_row_to_original = {}  # 映射显示行号到原始行号
        
        # 保存原始的 SN/ID 输入框内容
        self.original_sn_text = ""
        self.original_id_text = ""
        self.original_sn_list = []  # 原始 SN 列表
        self.original_id_list = []  # 原始 ID 列表
        
        # 列宽管理
        self.column_width_ratios = {}
        self.resize_timer = None
        
        # 缓存的 DeviceQuery 对象
        self._device_query = None
        self._device_query_env = None
        self._device_query_username = None
        self._device_query_password = None
        
        self.init_ui()
    
    def ensure_device_query(self, env, username, password):
        """
        确保 DeviceQuery 对象已初始化（使用缓存）
        如果凭证相同，则复用已有对象；否则创建新对象
        """
        # 检查是否需要创建新对象
        if (self._device_query is None or 
            self._device_query_env != env or 
            self._device_query_username != username or 
            self._device_query_password != password):
            
            # 创建新的 DeviceQuery 对象
            self._device_query = DeviceQuery(env, username, password)
            self._device_query_env = env
            self._device_query_username = username
            self._device_query_password = password
        
        return self._device_query
    
    def init_ui(self):
        """初始化UI"""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)

        # 使用QSplitter实现可拖拽调整高度
        splitter = QSplitter(Qt.Vertical)
        StyleManager.apply_to_widget(splitter, "SPLITTER")
        
        # 顶部查询区
        top_widget = self.create_query_group()
        
        # 底部结果与导出区
        bottom_widget = self.create_result_group()
        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        splitter.setHandleWidth(1)
        
        page_layout.addWidget(splitter)
    
    def create_query_group(self):
        """创建设备查询分组"""
        from PyQt5.QtWidgets import QGroupBox
        
        group = QGroupBox("设备查询")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # 标签行
        label_layout = QHBoxLayout()
        sn_label = QLabel("输入SN（每行一个）")
        id_label = QLabel("输入ID（每行一个）")
        label_layout.addWidget(sn_label, 1)
        label_layout.addSpacing(1)  # 分割线宽度
        label_layout.addWidget(id_label, 1)
        label_layout.addSpacing(88)
        group_layout.addLayout(label_layout)
        
        # 输入框和按钮行
        input_layout = QHBoxLayout()
        
        # SN输入框
        self.sn_input = PlainTextEdit()
        self.sn_input.setMinimumHeight(80)
        self.sn_input.setPlaceholderText("")
        self.sn_input.selectionChanged.connect(self.on_text_selection_changed)
        self.sn_input.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
            QTextEdit:focus {
                border: 1px solid #555555;
            }
        """)
        
        # ID输入框
        self.id_input = PlainTextEdit()
        self.id_input.setMinimumHeight(80)
        self.id_input.setPlaceholderText("")
        self.id_input.selectionChanged.connect(self.on_text_selection_changed)
        self.id_input.setStyleSheet("""
            QTextEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
            QTextEdit:focus {
                border: 1px solid #555555;
            }
        """)

        # 按钮
        btn_widget = QWidget()
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        # 线程数控件行
        thread_layout = QHBoxLayout()
        thread_layout.setContentsMargins(0, 0, 0, 0)
        thread_layout.setSpacing(0)
        thread_label = QLabel("线程:")
        self.thread_count_combo = NoWheelComboBox()
        # 填充 10-70，间隔 10
        for i in range(10, 71, 10):
            self.thread_count_combo.addItem(str(i))
        self.thread_count_combo.setCurrentText("40")
        self.thread_count_combo.setFixedWidth(50)
        self.thread_count_combo.currentTextChanged.connect(self.on_thread_count_changed)
        thread_layout.addWidget(thread_label)
        thread_layout.addWidget(self.thread_count_combo)
        thread_layout.addStretch()
        
        self.query_btn = QPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedSize(80, 28)
        self.query_btn.clicked.connect(self.on_query)
        
        self.clear_btn = QPushButton("清空")
        self.clear_btn.setIcon(QIcon(":/icons/common/clean.png"))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setFixedSize(80, 28)
        self.clear_btn.clicked.connect(self.on_clear)
        
        btn_layout.addStretch()
        btn_layout.addLayout(thread_layout)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.query_btn)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        
        input_layout.addWidget(self.sn_input, 1)
        
        # 添加第一条垂直分割线
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Plain)
        separator1.setFixedWidth(1)
        separator1.setStyleSheet("QFrame { background-color: #555555; border: none; }")
        input_layout.addWidget(separator1)
        
        input_layout.addWidget(self.id_input, 1)
        
        # 添加第二条垂直分割线
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Plain)
        separator2.setFixedWidth(1)
        separator2.setStyleSheet("QFrame { background-color: #555555; border: none; }")
        input_layout.addWidget(separator2)
        
        input_layout.addWidget(btn_widget)
        group_layout.addLayout(input_layout)
        
        return group
    
    def create_result_group(self):
        """创建查询结果与导出分组"""
        from PyQt5.QtWidgets import QGroupBox
        
        group = QGroupBox("查询结果与导出")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # 结果区标题和批量唤醒按钮
        result_header = QHBoxLayout()
        
        self.select_all_checkbox = QCheckBox("全选")
        self.select_all_checkbox.stateChanged.connect(self.on_select_all)
        self.select_all_checkbox.setEnabled(False)  # 初始禁用
        
        self.batch_wake_btn = QPushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(100, 28)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        self.batch_wake_btn.setEnabled(False)  # 初始禁用
        
        # 版本号下拉框
        version_label = QLabel("版本:")
        self.version_combo = NoWheelComboBox()
        self.version_combo.addItem("全部")
        self.version_combo.setEnabled(False)
        self.version_combo.currentTextChanged.connect(self.on_version_changed)
        
        # 匹配数量标签
        quantity_label = QLabel("数量:")
        self.match_count_label = QLabel("0")
        self.match_count_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        
        result_tip = QLabel("双击表格复制")
        result_tip.setStyleSheet("color: #909090; font-size: 11px;")
        
        result_header.addWidget(self.select_all_checkbox)
        result_header.addWidget(self.batch_wake_btn)
        result_header.addSpacing(20)
        result_header.addWidget(version_label)
        result_header.addWidget(self.version_combo, 1)
        result_header.addSpacing(20)
        result_header.addWidget(quantity_label)
        self.match_count_label.setText("0")
        result_header.addWidget(self.match_count_label)
        result_header.addSpacing(20)
        result_header.addWidget(result_tip)
        group_layout.addLayout(result_header)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(10)
        self.result_table.setHorizontalHeaderLabels(
            ["选择", "设备名称", "SN", "ID", "密码", "接入节点", "版本号", "在线状态", "最后心跳", "操作"]
        )
        self.result_table.setFocusPolicy(Qt.StrongFocus)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        self.result_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setShowGrid(True)
        self.result_table.setFrameShape(QTableWidget.NoFrame)
        StyleManager.apply_to_widget(self.result_table, "TABLE")
        
        # 设置列宽
        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        for col in range(1, 9):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        self.result_table.setColumnWidth(0, 50)
        self.result_table.setColumnWidth(9, 140)
        col_width = (600 - 50 - 140) // 8
        for col in range(1, 9):
            self.result_table.setColumnWidth(col, col_width)
        
        # 初始化列宽比例
        self.column_width_ratios = {col: col_width for col in range(1, 9)}
        
        # 连接列宽变化事件
        header.sectionResized.connect(self.on_column_resized)
        
        # 连接双击复制事件
        self.result_table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # 连接单击事件
        self.result_table.cellClicked.connect(self.on_cell_clicked)
        
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        group_layout.addWidget(self.result_table)
        
        # 导出区域
        export_layout = QHBoxLayout()
        export_label = QLabel("保存位置:")
        export_label.setFixedWidth(70)
        export_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.export_path_input = ClickableLineEdit()
        self.export_path_input.setPlaceholderText("点击导出按钮选择保存位置（双击可打开目录）...")
        self.export_path_input.setReadOnly(True)
        self.export_path_input.setFocusPolicy(Qt.NoFocus)
        self.export_path_input.setMinimumHeight(28)
        self.export_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 4px;
            }
        """)
        
        self.export_btn = QPushButton("导出")
        self.export_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(80, 28)
        self.export_btn.clicked.connect(self.on_export_csv)
        
        export_layout.addWidget(export_label)
        export_layout.addWidget(self.export_path_input, 1)
        export_layout.addWidget(self.export_btn)
        group_layout.addLayout(export_layout)
        
        # 创建按钮组
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(
            self.query_btn, self.clear_btn, self.batch_wake_btn,
            self.select_all_checkbox, self.export_btn
        )
        
        return group

    def on_page_show(self):
        """页面显示时"""
        self.show_info("设备页面")
        # 调整表格列宽以适应当前窗口
        self.adjust_table_columns()
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self.adjust_table_columns()
    
    def on_column_resized(self, logicalIndex):
        """列宽被用户调节时，使用防抖机制延迟调整其他列"""
        # 跳过固定列
        if logicalIndex == 0 or logicalIndex == 9:
            return
        
        # 如果已有待处理的调整，取消它
        if self.resize_timer is not None:
            self.resize_timer.stop()
        
        # 创建新的防抖计时器（200ms 延迟）
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self._do_column_resize(logicalIndex))
        self.resize_timer.start(200)
    
    def _do_column_resize(self, logicalIndex):
        """实际执行列宽调整"""
        # 获取表格可用宽度（减去固定列）
        table_width = self.result_table.width()
        fixed_width = 50 + 140  # 选择列 + 操作列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 9))
        
        # 如果总宽度不等于可用宽度，调整其他列
        if current_total != available_width:
            # 计算差值
            diff = available_width - current_total
            
            # 从其他列均匀调整
            other_cols = [col for col in range(1, 9) if col != logicalIndex]
            if other_cols:
                adjustment_per_col = diff / len(other_cols)
                for col in other_cols:
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(50, int(current_width + adjustment_per_col))
                    self.result_table.setColumnWidth(col, new_width)
        
        # 更新该列的比例
        new_width = self.result_table.columnWidth(logicalIndex)
        if logicalIndex in self.column_width_ratios:
            self.column_width_ratios[logicalIndex] = new_width
    
    def adjust_table_columns(self):
        """根据窗口宽度调整表格列宽，保持表格宽度与窗口一致"""
        # 获取表格可用宽度（减去固定列）
        table_width = self.result_table.width()
        fixed_width = 50 + 140  # 选择列 + 操作列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 9))
        
        # 如果当前总宽度不等于可用宽度，需要调整
        if current_total != available_width:
            # 计算缩放因子
            if current_total > 0:
                scale_factor = available_width / current_total
                
                # 按比例调整每列宽度
                for col in range(1, 9):
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(50, int(current_width * scale_factor))
                    self.result_table.setColumnWidth(col, new_width)
    
    def on_text_selection_changed(self):
        """文本选中状态改变"""
        sn_cursor = self.sn_input.textCursor()
        sn_selected_text = sn_cursor.selectedText().replace('\u2029', '\n')
        sn_lines = len([line for line in sn_selected_text.split('\n') if line.strip()]) if sn_selected_text else 0
        
        id_cursor = self.id_input.textCursor()
        id_selected_text = id_cursor.selectedText().replace('\u2029', '\n')
        id_lines = len([line for line in id_selected_text.split('\n') if line.strip()]) if id_selected_text else 0
        
        total_lines = sn_lines + id_lines
        if total_lines > 0:
            self.show_info(f"已选中 {total_lines} 行数据")
        else:
            self.show_info("就绪")
    
    def on_cell_double_clicked(self, row, column):
        """表格单元格双击复制"""
        # 跳过选择列和操作列
        if column == 0 or column == 9:
            return
        
        item = self.result_table.item(row, column)
        if item:
            text = item.text()
            if text and text not in ["查询中...", ""]:
                from PyQt5.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                
                # 选中当前单元格
                self.result_table.setCurrentCell(row, column)
                
                self.show_success(f"已复制: {text}", 2000)
    
    def on_cell_clicked(self, row, column):
        """表格单元格单击"""
        # 跳过选择列和操作列
        if column == 0 or column == 9:
            # 清除选中状态
            self.result_table.clearSelection()
            return
        
        # 选中当前单元格
        self.result_table.setCurrentCell(row, column)
    
    def on_thread_count_changed(self, text):
        """线程数改变事件"""
        self.thread_count = int(text)
    
    def on_query(self):
        """查询按钮点击"""
        sn_text = self.sn_input.toPlainText().strip()
        id_text = self.id_input.toPlainText().strip()
        
        if not sn_text and not id_text:
            self.show_warning("请输入SN/ID信息")
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
        
        # 解析输入
        sn_list = [line.strip() for line in sn_text.split('\n') if line.strip()]
        id_list = [line.strip() for line in id_text.split('\n') if line.strip()]
        
        # 判断查询类型
        if self.query_input_type == 'sn' and sn_list:
            id_list = []
            self.query_input_list = sn_list
        elif self.query_input_type == 'id' and id_list:
            sn_list = []
            self.query_input_list = id_list
        else:
            if sn_list and not id_list:
                self.query_input_type = 'sn'
                self.query_input_list = sn_list
            elif id_list and not sn_list:
                self.query_input_type = 'id'
                self.query_input_list = id_list
            else:
                self.query_input_type = None
                self.query_input_list = []
        
        # 重置数据
        self.query_results = {}
        self.total_count = len(sn_list) + len(id_list)
        self.online_count = 0
        self.offline_count = 0
        
        # 禁用按钮
        self.main_buttons.disable()
        self.query_btn.setText("查询中...")
        
        # 清理旧的查询线程
        if hasattr(self, '_query_thread') and self._query_thread:
            try:
                self._query_thread.stop()
                self._query_thread.quit()
                self._query_thread.wait(timeout=2000)
            except:
                pass
        
        # 启动查询线程
        query_thread = QueryThread(sn_list, id_list, env, username, password, max_workers=self.thread_count)
        query_thread.init_success.connect(self.on_query_init_success)
        query_thread.single_result.connect(self.on_single_result)
        query_thread.all_done.connect(self.on_query_complete)
        query_thread.progress.connect(lambda msg: self.show_progress(msg))
        query_thread.error.connect(self.on_query_error)
        
        # 连接 finished 信号进行清理
        query_thread.finished.connect(lambda: self.thread_mgr.cleanup("query"))
        
        # 保存线程引用
        self._query_thread = query_thread
        self.thread_mgr.add("query", query_thread)
        query_thread.start()

    def on_query_init_success(self):
        """查询初始化成功"""
        self.result_table.setRowCount(self.total_count)
        self.display_row_to_original = {}
        
        # 初始化行号映射
        for row in range(self.total_count):
            self.display_row_to_original[row] = row
        
        # 批量创建行（每 50 行一批）
        batch_size = 50
        for batch_start in range(0, self.total_count, batch_size):
            batch_end = min(batch_start + batch_size, self.total_count)
            
            for row in range(batch_start, batch_end):
                # 复选框
                checkbox = QCheckBox()
                checkbox_widget = QWidget()
                checkbox_widget.setStyleSheet("background-color: transparent;")
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.result_table.setCellWidget(row, 0, checkbox_widget)
                
                # 占位
                self.result_table.setItem(row, 1, QTableWidgetItem("查询中..."))
                for col in range(2, 9):
                    self.result_table.setItem(row, col, QTableWidgetItem(""))
                
                # 唤醒按钮
                wake_btn = QPushButton("唤醒")
                wake_btn.setIcon(QIcon(":/icons/device/werk_up.png"))
                wake_btn.setIconSize(QSize(16, 16))
                wake_btn.setFocusPolicy(Qt.NoFocus)
                wake_btn.setEnabled(False)
                wake_btn.clicked.connect(lambda checked, r=row: self.on_wake_single(r))
                
                btn_container = QWidget()
                btn_container.setStyleSheet("background-color: transparent;")
                btn_layout = QHBoxLayout(btn_container)
                btn_layout.addStretch()
                btn_layout.addWidget(wake_btn)
                btn_layout.addStretch()
                btn_layout.setContentsMargins(0, 0, 0, 0)
                btn_layout.setSpacing(0)
                self.result_table.setCellWidget(row, 9, btn_container)
        
        # 重新启用表格更新
        self.result_table.setUpdatesEnabled(True)
        self.result_table.viewport().update()
    
    def on_single_result(self, row, item):
        """单个设备查询完成"""
        # 添加空指针检查
        if item is None:
            self.show_error(f"第 {row} 行数据为空")
            return
        
        if not isinstance(item, dict):
            self.show_error(f"第 {row} 行数据格式错误")
            return
        
        self.query_results[row] = item
        
        # 安全地获取值，提供默认值
        device_name = item.get('device_name', '')
        sn = item.get('sn', '')
        dev_id = item.get('id', '')
        password = item.get('password', '')
        node = item.get('node', '')
        version = item.get('version', '')
        last_heartbeat = item.get('last_heartbeat', '')
        
        self.result_table.setItem(row, 1, QTableWidgetItem(device_name))
        self.result_table.setItem(row, 2, QTableWidgetItem(sn))
        self.result_table.setItem(row, 3, QTableWidgetItem(dev_id))
        self.result_table.setItem(row, 4, QTableWidgetItem(password))
        self.result_table.setItem(row, 5, QTableWidgetItem(str(node)))
        self.result_table.setItem(row, 6, QTableWidgetItem(version))
        
        # 在线状态
        online_status = item.get('online', -1)
        if online_status == 1:
            status_text = "在线"
            status_color = Qt.green
            self.online_count += 1
        elif online_status == 0:
            status_text = "离线"
            status_color = Qt.red
            self.offline_count += 1
        elif online_status == -1:
            status_text = "未找到"
            status_color = Qt.gray
        else:
            status_text = "查询失败"
            status_color = Qt.darkYellow
        
        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(status_color)
        self.result_table.setItem(row, 7, status_item)
        
        # 最后心跳
        self.result_table.setItem(row, 8, QTableWidgetItem(last_heartbeat))
    
    def on_query_error(self, error_msg):
        """查询出错"""
        self.main_buttons.enable()
        self.show_error(f"查询失败: {error_msg}")
    
    def on_query_complete(self):
        """查询完成"""
        self.main_buttons.enable()
        
        # 启用所有唤醒按钮
        for row in range(self.result_table.rowCount()):
            btn_container = self.result_table.cellWidget(row, 9)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setEnabled(True)
        
        # 填充对应的输入框并保存原始列表
        if self.query_input_type == 'sn':
            id_results = []
            for input_sn in self.query_input_list:
                found = False
                for row, result in self.query_results.items():
                    if result['sn'] == input_sn:
                        id_results.append(result['id'])
                        found = True
                        break
                if not found:
                    id_results.append("不存在")
            self.id_input.setPlainText('\n'.join(id_results))
            # 保存原始列表
            self.original_sn_list = self.query_input_list.copy()
            self.original_id_list = id_results.copy()
            self.original_sn_text = self.sn_input.toPlainText()
            self.original_id_text = self.id_input.toPlainText()
        elif self.query_input_type == 'id':
            sn_results = []
            for input_id in self.query_input_list:
                found = False
                for row, result in self.query_results.items():
                    if result['id'] == input_id:
                        sn_results.append(result['sn'])
                        found = True
                        break
                if not found:
                    sn_results.append("不存在")
            self.sn_input.setPlainText('\n'.join(sn_results))
            # 保存原始列表
            self.original_sn_list = sn_results.copy()
            self.original_id_list = self.query_input_list.copy()
            self.original_sn_text = self.sn_input.toPlainText()
            self.original_id_text = self.id_input.toPlainText()
        
        self.show_success(
            f"查询完成：共 {self.total_count} 台设备，在线 {self.online_count} 台，离线 {self.offline_count} 台"
        )
        
        # 查询完成后启用全选框
        if self.result_table.rowCount() > 0:
            self.select_all_checkbox.setEnabled(True)
        else:
            self.select_all_checkbox.setEnabled(False)
        
        # 收集所有版本号并更新下拉框
        self.update_version_combo()
        
        # 初始化匹配数量为全部数量
        self.match_count_label.setText(f"{self.result_table.rowCount()}")

    def on_clear(self):
        """清空按钮点击"""
        self.sn_input.clear()
        self.id_input.clear()
        self.result_table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        self.query_input_type = None
        self.query_input_list = []
        self.query_results = {}
        
        # 清空后禁用全选框和批量唤醒按钮
        self.select_all_checkbox.setEnabled(False)
        self.batch_wake_btn.setEnabled(False)
        
        # 重置版本下拉框
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        self.version_combo.setEnabled(False)
        self.version_combo.blockSignals(False)
        self.all_versions = set()
        self.current_version_filter = None
        self.filtered_results = {}
        
        # 重置匹配数量
        self.match_count_label.setText("0")
        
        # 重置原始文本和列表
        self.original_sn_text = ""
        self.original_id_text = ""
        self.original_sn_list = []
        self.original_id_list = []
        
        self.show_success("清空完成")
    
    def on_select_all(self, state):
        """全选/取消全选"""
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(state == Qt.Checked)
        
        # 根据全选框状态控制批量唤醒按钮
        self.batch_wake_btn.setEnabled(state == Qt.Checked)
    
    def on_wake_single(self, row):
        """单个设备唤醒"""
        # 获取原始行号
        original_row = self.display_row_to_original.get(row, row)
        
        sn = self.result_table.item(row, 2).text()
        dev_id = self.result_table.item(row, 3).text()
        
        if not sn or not dev_id:
            self.show_warning("设备信息不完整，无法唤醒")
            return
        
        self.result_table.clearSelection()
        
        # 显示开始唤醒的提示
        self.show_progress(f"正在唤醒 {sn}...")
        
        # 获取按钮
        btn_container = self.result_table.cellWidget(row, 9)
        wake_btn = btn_container.findChild(QPushButton) if btn_container else None
        
        if wake_btn:
            wake_btn.setText("唤醒中...")
            wake_btn.setEnabled(False)
        
        # 唤醒
        try:
            env, username, password = get_account_config()
            # 使用缓存的 DeviceQuery 对象
            query = self.ensure_device_query(env, username, password)
            if query.init_error:
                if wake_btn:
                    wake_btn.setText("唤醒")
                    wake_btn.setEnabled(True)
                self.show_error(query.init_error)
                return
            
            wake_thread = WakeThread([(dev_id, sn)], query, max_workers=1)
            wake_thread.wake_result.connect(lambda name, success: self.on_single_wake_done(row, wake_btn, sn, success))
            wake_thread.finished.connect(lambda: self.thread_mgr.cleanup("wake_single"))
            self.thread_mgr.add("wake_single", wake_thread)
            wake_thread.start()
        except Exception as e:
            if wake_btn:
                wake_btn.setText("唤醒")
                wake_btn.setEnabled(True)
            self.show_error(f"唤醒失败: {str(e)}")
    
    def on_single_wake_done(self, row, wake_btn, sn, success):
        """单个唤醒完成"""
        if wake_btn:
            wake_btn.setText("唤醒")
            wake_btn.setEnabled(True)
        
        if success:
            try:
                env, username, password = get_account_config()
                # 使用缓存的 DeviceQuery 对象
                query = self.ensure_device_query(env, username, password)
                if not query.init_error:
                    is_online = check_device_online(sn, query.token)
                    status_text = "在线" if is_online else "离线"
                    status_color = Qt.green if is_online else Qt.red
                    
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(status_color)
                    self.result_table.setItem(row, 7, status_item)
            except Exception as e:
                pass
        
        # 唤醒完成后，重新统计在线离线数量并显示
        self.update_device_status_summary()

    def on_batch_wake(self):
        """批量唤醒"""
        selected_devices = []
        selected_rows = []
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                sn = self.result_table.item(row, 2).text()
                dev_id = self.result_table.item(row, 3).text()
                if sn and dev_id:
                    selected_devices.append((dev_id, sn))
                    selected_rows.append(row)
        
        if not selected_devices:
            self.show_warning("请先选择要唤醒的设备")
            return
        
        # 禁用按钮
        self.main_buttons.disable()
        self.batch_wake_btn.setText("唤醒中...")
        
        # 禁用唤醒按钮
        for row in selected_rows:
            btn_container = self.result_table.cellWidget(row, 9)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setText("唤醒中...")
                wake_btn.setEnabled(False)
        
        # 启动唤醒线程
        try:
            env, username, password = get_account_config()
            # 使用缓存的 DeviceQuery 对象
            query = self.ensure_device_query(env, username, password)
            if query.init_error:
                self.main_buttons.enable()
                for row in selected_rows:
                    btn_container = self.result_table.cellWidget(row, 9)
                    wake_btn = btn_container.findChild(QPushButton) if btn_container else None
                    if wake_btn:
                        wake_btn.setText("唤醒")
                        wake_btn.setEnabled(True)
                self.show_error(query.init_error)
                return
            
            wake_thread = WakeThread(selected_devices, query, max_workers=self.thread_count)
            wake_thread.wake_result.connect(lambda name, success: self.on_wake_result(name, success, selected_rows))
            wake_thread.all_done.connect(lambda: self.on_wake_complete(selected_rows))
            wake_thread.progress.connect(lambda msg: self.show_progress(msg))
            wake_thread.error.connect(lambda msg: self.show_error(f"唤醒失败: {msg}"))
            
            self.thread_mgr.add("wake", wake_thread)
            wake_thread.start()
        except Exception as e:
            self.main_buttons.enable()
            for row in selected_rows:
                btn_container = self.result_table.cellWidget(row, 9)
                wake_btn = btn_container.findChild(QPushButton) if btn_container else None
                if wake_btn:
                    wake_btn.setText("唤醒")
                    wake_btn.setEnabled(True)
            self.show_error(f"初始化失败: {str(e)}")
    
    def on_wake_result(self, device_name, success, selected_rows):
        """唤醒结果"""
        if success and selected_rows:
            for row in selected_rows:
                sn = self.result_table.item(row, 2).text()
                if device_name.startswith(sn):
                    try:
                        env, username, password = get_account_config()
                        # 使用缓存的 DeviceQuery 对象
                        query = self.ensure_device_query(env, username, password)
                        if not query.init_error:
                            is_online = check_device_online(sn, query.token)
                            status_text = "在线" if is_online else "离线"
                            status_color = Qt.green if is_online else Qt.red
                            
                            status_item = QTableWidgetItem(status_text)
                            status_item.setForeground(status_color)
                            self.result_table.setItem(row, 7, status_item)
                    except Exception as e:
                        pass
                    break
    
    def on_wake_complete(self, selected_rows):
        """唤醒完成"""
        self.main_buttons.enable()
        
        # 恢复唤醒按钮
        for row in selected_rows:
            btn_container = self.result_table.cellWidget(row, 9)
            wake_btn = btn_container.findChild(QPushButton) if btn_container else None
            if wake_btn:
                wake_btn.setText("唤醒")
                wake_btn.setEnabled(True)
        
        # 唤醒完成后，重新统计在线离线数量并显示
        self.update_device_status_summary()

    def on_export_csv(self):
        """导出CSV"""
        if self.result_table.rowCount() == 0:
            self.show_warning("没有可导出的数据")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"设备信息_{timestamp}.csv"
            initial_dir = self.export_path if self.export_path else os.path.expanduser("~")
            default_path = os.path.join(initial_dir, default_filename)
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存CSV文件", default_path, "CSV文件 (*.csv);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
            
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'
            
            self.export_path = os.path.dirname(file_path)
            self.export_path_input.setText(self.export_path)
            
            count = TableHelper.export_to_csv(
                self.result_table,
                file_path=file_path,
                columns={1: "设备名称", 2: "SN", 3: "ID", 4: "密码"},
                skip_text=["查询中..."]
            )
            
            filename = os.path.basename(file_path)
            self.show_success(f"导出成功：{filename}（共{count}条数据）")
        except Exception as e:
            self.show_error(f"导出失败：{str(e)}")
    
    def update_device_status_summary(self):
        """更新设备状态统计信息"""
        total = self.result_table.rowCount()
        online = 0
        offline = 0
        
        # 遍历表格统计在线离线数量
        for row in range(total):
            status_item = self.result_table.item(row, 7)
            if status_item:
                status_text = status_item.text()
                if status_text == "在线":
                    online += 1
                elif status_text == "离线":
                    offline += 1
        
        # 显示统计信息
        self.show_success(f"查询完成：共 {total} 台设备，在线 {online} 台，离线 {offline} 台")
    
    def update_filtered_status_summary(self):
        """更新过滤后的设备状态统计信息"""
        total = self.result_table.rowCount()
        online = 0
        offline = 0
        
        # 遍历表格统计在线离线数量
        for row in range(total):
            status_item = self.result_table.item(row, 7)
            if status_item:
                status_text = status_item.text()
                if status_text == "在线":
                    online += 1
                elif status_text == "离线":
                    offline += 1
        
        # 显示过滤后的统计信息
        self.show_success(f"筛选完成：共 {total} 台设备，在线 {online} 台，离线 {offline} 台")
    
    def update_version_combo(self):
        """更新版本下拉框"""
        # 收集所有版本号
        self.all_versions = set()
        for row, result in self.query_results.items():
            version = result.get('version', '')
            if version:
                self.all_versions.add(version)
        
        # 更新下拉框
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        
        # 按版本号排序添加
        for version in sorted(self.all_versions):
            self.version_combo.addItem(version)
        
        self.version_combo.setEnabled(len(self.all_versions) > 0)
        self.version_combo.blockSignals(False)
        
        # 重置过滤
        self.current_version_filter = None
        self.filtered_results = {}
    
    def on_version_changed(self, version):
        """版本下拉框改变"""
        if version == "全部":
            # 显示所有数据
            self.current_version_filter = None
            self.filtered_results = {}
            self.refresh_table_display()
            # 更新匹配数量
            self.match_count_label.setText(f"{self.result_table.rowCount()}")
            # 恢复原始输入框内容
            self.sn_input.setPlainText(self.original_sn_text)
            self.id_input.setPlainText(self.original_id_text)
            # 显示原始统计信息
            self.show_success(
                f"查询完成：共 {self.total_count} 台设备，在线 {self.online_count} 台，离线 {self.offline_count} 台"
            )
        else:
            # 过滤指定版本的数据
            self.current_version_filter = version
            self.filtered_results = {}
            
            for row, result in self.query_results.items():
                if result.get('version', '') == version:
                    self.filtered_results[row] = result
            
            self.refresh_table_display()
            # 更新匹配数量
            self.match_count_label.setText(f"{self.result_table.rowCount()}")
            # 更新输入框为过滤后的数据
            self.update_input_boxes_from_filtered_results()
            # 统计过滤后的在线离线数量
            self.update_filtered_status_summary()
    
    def refresh_table_display(self):
        """刷新表格显示"""
        # 确定要显示的数据
        display_data = self.filtered_results if self.current_version_filter else self.query_results
        
        # 清空表格
        self.result_table.setRowCount(0)
        self.display_row_to_original = {}
        
        if not display_data:
            return
        
        # 重新填充表格
        self.result_table.setRowCount(len(display_data))
        
        for display_row, (original_row, item) in enumerate(sorted(display_data.items())):
            # 保存行号映射
            self.display_row_to_original[display_row] = original_row
            
            # 复选框
            checkbox = QCheckBox()
            checkbox_widget = QWidget()
            checkbox_widget.setStyleSheet("background-color: transparent;")
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(display_row, 0, checkbox_widget)
            
            # 数据
            device_name = item.get('device_name', '')
            sn = item.get('sn', '')
            dev_id = item.get('id', '')
            password = item.get('password', '')
            node = item.get('node', '')
            version = item.get('version', '')
            last_heartbeat = item.get('last_heartbeat', '')
            
            self.result_table.setItem(display_row, 1, QTableWidgetItem(device_name))
            self.result_table.setItem(display_row, 2, QTableWidgetItem(sn))
            self.result_table.setItem(display_row, 3, QTableWidgetItem(dev_id))
            self.result_table.setItem(display_row, 4, QTableWidgetItem(password))
            self.result_table.setItem(display_row, 5, QTableWidgetItem(str(node)))
            self.result_table.setItem(display_row, 6, QTableWidgetItem(version))
            
            # 在线状态
            online_status = item.get('online', -1)
            if online_status == 1:
                status_text = "在线"
                status_color = Qt.green
            elif online_status == 0:
                status_text = "离线"
                status_color = Qt.red
            elif online_status == -1:
                status_text = "未找到"
                status_color = Qt.gray
            else:
                status_text = "查询失败"
                status_color = Qt.darkYellow
            
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            self.result_table.setItem(display_row, 7, status_item)
            
            # 最后心跳
            self.result_table.setItem(display_row, 8, QTableWidgetItem(last_heartbeat))
            
            # 唤醒按钮
            wake_btn = QPushButton("唤醒")
            wake_btn.setIcon(QIcon(":/icons/device/werk_up.png"))
            wake_btn.setIconSize(QSize(16, 16))
            wake_btn.setFocusPolicy(Qt.NoFocus)
            wake_btn.clicked.connect(lambda checked, r=display_row: self.on_wake_single(r))
            
            btn_container = QWidget()
            btn_container.setStyleSheet("background-color: transparent;")
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addStretch()
            btn_layout.addWidget(wake_btn)
            btn_layout.addStretch()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setSpacing(0)
            self.result_table.setCellWidget(display_row, 9, btn_container)
        
        # 重新启用表格更新
        self.result_table.setUpdatesEnabled(True)
        self.result_table.viewport().update()
    
    def update_input_boxes_from_table(self):
        """根据表格内容更新输入框"""
        sn_list = []
        id_list = []
        
        for row in range(self.result_table.rowCount()):
            sn_item = self.result_table.item(row, 2)
            id_item = self.result_table.item(row, 3)
            
            if sn_item:
                sn = sn_item.text()
                if sn:
                    sn_list.append(sn)
            
            if id_item:
                dev_id = id_item.text()
                if dev_id:
                    id_list.append(dev_id)
        
        # 根据原始查询类型更新对应的输入框
        if self.query_input_type == 'sn':
            self.id_input.setPlainText('\n'.join(id_list))
        elif self.query_input_type == 'id':
            self.sn_input.setPlainText('\n'.join(sn_list))
    
    def update_input_boxes_from_filtered_results(self):
        """根据过滤结果更新输入框"""
        sn_list = []
        id_list = []
        
        # 从过滤结果中提取 SN 和 ID
        for row, result in sorted(self.filtered_results.items()):
            sn = result.get('sn', '')
            dev_id = result.get('id', '')
            if sn:
                sn_list.append(sn)
            if dev_id:
                id_list.append(dev_id)
        
        # 同时更新两个输入框
        self.sn_input.setPlainText('\n'.join(sn_list))
        self.id_input.setPlainText('\n'.join(id_list))
    
    def load_config(self):
        """加载配置"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        if app_config.export_path:
            self.export_path = app_config.export_path
            self.export_path_input.setText(app_config.export_path)
    
    def save_config(self):
        """保存配置"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        app_config.export_path = self.export_path
        config_manager.save_app_config(app_config)
    
    def cleanup(self):
        """清理资源"""
        self.thread_mgr.stop_all()
