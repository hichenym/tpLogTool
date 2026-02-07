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
from PyQt5.QtGui import QIcon, QColor

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import (
    ButtonManager, MessageManager, ThreadManager, StyleManager, TableHelper,
    get_account_config, DeviceQuery, check_device_online
)
from query_tool.utils.workers import QueryThread, WakeThread, PhoneQueryThread
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
        
        # 账号查询相关
        self.phone_query_results = []
        
        # 筛选相关
        self.all_models = set()  # 所有型号
        self.all_versions = set()  # 所有版本
        self.current_sn_filter = ""  # 当前SN筛选
        self.current_model_filter = None  # 当前型号筛选
        self.current_version_filter = None  # 当前版本筛选
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
        
        # 设置分割线样式：增加上下边距，使用柔和的颜色提示可拖动
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #707070;
                margin: 6px 0px;
            }
            QSplitter::handle:hover {
                background-color: #909090;
            }
            QSplitter::handle:pressed {
                background-color: #A0A0A0;
            }
        """)
        
        # 顶部查询区
        top_widget = self.create_query_group()
        
        # 底部结果与导出区
        bottom_widget = self.create_result_group()
        
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        
        page_layout.addWidget(splitter)
    
    def create_query_group(self):
        """创建设备查询分组"""
        from PyQt5.QtWidgets import QGroupBox, QLineEdit, QCompleter
        
        group = QGroupBox("查询")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # ===== 账号查询区（带边框） =====
        account_frame = QFrame()
        account_frame.setFrameShape(QFrame.StyledPanel)
        account_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                background-color: transparent;
            }
        """)
        account_frame.setFixedHeight(44)  # 设置固定高度，与其他区域保持一致
        account_frame_layout = QHBoxLayout(account_frame)
        account_frame_layout.setContentsMargins(8, 8, 8, 8)
        account_frame_layout.setSpacing(10)
        
        account_label = QLabel("账号:")
        account_label.setFixedWidth(35)
        account_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        account_label.setStyleSheet("border: none;")  # 去掉边框
        
        self.phone_input = NoWheelComboBox()
        self.phone_input.setEditable(True)
        self.phone_input.setInsertPolicy(QComboBox.NoInsert)
        self.phone_input.setFocusPolicy(Qt.StrongFocus)
        self.phone_input.lineEdit().setPlaceholderText("请输入账号...")
        self.phone_input.setFixedHeight(28)
        
        self.phone_query_btn = QPushButton("账号查询")
        self.phone_query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.phone_query_btn.setIconSize(QSize(16, 16))
        self.phone_query_btn.setFixedSize(90, 28)  # 统一按钮宽度为90px
        self.phone_query_btn.clicked.connect(self.on_phone_query)
        
        account_frame_layout.addWidget(account_label)
        account_frame_layout.addWidget(self.phone_input, 1)
        account_frame_layout.addWidget(self.phone_query_btn)
        group_layout.addWidget(account_frame)
        
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
        thread_layout.setSpacing(5)
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
        
        self.query_btn = QPushButton("设备查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedSize(90, 28)  # 统一按钮宽度为90px
        self.query_btn.clicked.connect(self.on_query)
        
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.setIcon(QIcon(":/icons/common/clean.png"))
        self.clear_btn.setIconSize(QSize(16, 16))
        self.clear_btn.setFixedSize(90, 28)  # 统一按钮宽度为90px
        self.clear_btn.clicked.connect(self.on_clear)
        
        btn_layout.addStretch()
        btn_layout.addLayout(thread_layout)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.query_btn, 0, Qt.AlignRight)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(self.clear_btn, 0, Qt.AlignRight)
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
        from PyQt5.QtWidgets import QGroupBox, QLineEdit
        
        group = QGroupBox("结果")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # ===== 筛选条件区 =====
        filter_frame = QFrame()
        filter_frame.setFrameShape(QFrame.StyledPanel)
        filter_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                background-color: transparent;
            }
        """)
        filter_frame.setFixedHeight(44)  # 设置固定高度，与其他区域保持一致
        filter_layout = QHBoxLayout(filter_frame)  # 改为水平布局，单行显示
        filter_layout.setContentsMargins(8, 8, 8, 8)
        filter_layout.setSpacing(10)
        
        # SN筛选
        sn_filter_label = QLabel("SN:")
        sn_filter_label.setFixedWidth(30)
        sn_filter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sn_filter_label.setStyleSheet("border: none;")  # 去掉边框
        self.sn_filter_input = QLineEdit()
        self.sn_filter_input.setFixedHeight(28)
        self.sn_filter_input.setPlaceholderText("输入SN筛选...")
        self.sn_filter_input.textChanged.connect(self.on_filter_changed)
        self.sn_filter_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 4px;
            }
        """)
        
        # 型号筛选
        model_filter_label = QLabel("型号:")
        model_filter_label.setFixedWidth(40)
        model_filter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        model_filter_label.setStyleSheet("border: none;")  # 去掉边框
        self.model_combo = NoWheelComboBox()
        self.model_combo.setFixedHeight(28)
        self.model_combo.addItem("全部")
        self.model_combo.setEnabled(False)
        self.model_combo.currentTextChanged.connect(self.on_filter_changed)
        
        # 版本筛选
        version_filter_label = QLabel("版本:")
        version_filter_label.setFixedWidth(40)
        version_filter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        version_filter_label.setStyleSheet("border: none;")  # 去掉边框
        self.version_combo = NoWheelComboBox()
        self.version_combo.setFixedHeight(28)
        self.version_combo.addItem("全部")
        self.version_combo.setEnabled(False)
        self.version_combo.currentTextChanged.connect(self.on_filter_changed)
        
        # 数量显示
        self.match_count_label = QLabel("数量: 0 / 0")
        self.match_count_label.setStyleSheet("color: #e0e0e0; font-size: 12px; border: none;")  # 去掉边框
        
        # 按比例 1:1:3 添加控件
        filter_layout.addWidget(sn_filter_label)
        filter_layout.addWidget(self.sn_filter_input, 1)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(model_filter_label)
        filter_layout.addWidget(self.model_combo, 1)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(version_filter_label)
        filter_layout.addWidget(self.version_combo, 3)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(self.match_count_label)
        
        group_layout.addWidget(filter_frame)
        
        # ===== 批量操作区 =====
        batch_frame = QFrame()
        batch_frame.setFrameShape(QFrame.StyledPanel)
        batch_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                background-color: transparent;
            }
        """)
        batch_frame.setFixedHeight(44)  # 设置固定高度，与其他区域保持一致
        batch_layout = QHBoxLayout(batch_frame)
        batch_layout.setContentsMargins(8, 8, 8, 8)
        batch_layout.setSpacing(10)
        
        self.select_all_checkbox = QCheckBox("全选")
        self.select_all_checkbox.stateChanged.connect(self.on_select_all)
        self.select_all_checkbox.setEnabled(False)  # 初始禁用
        
        self.batch_wake_btn = QPushButton("批量唤醒")
        self.batch_wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.batch_wake_btn.setIconSize(QSize(16, 16))
        self.batch_wake_btn.setFixedSize(100, 28)
        self.batch_wake_btn.clicked.connect(self.on_batch_wake)
        self.batch_wake_btn.setEnabled(False)  # 初始禁用
        
        # 预留的批量操作按钮
        self.batch_reboot_btn = QPushButton("批量重启")
        self.batch_reboot_btn.setIcon(QIcon(":/icons/device/reboot.png"))
        self.batch_reboot_btn.setIconSize(QSize(16, 16))
        self.batch_reboot_btn.setFixedSize(100, 28)
        self.batch_reboot_btn.setEnabled(False)
        self.batch_reboot_btn.clicked.connect(self.on_batch_reboot)
        
        self.batch_upgrade_btn = QPushButton("批量升级")
        self.batch_upgrade_btn.setIcon(QIcon(":/icons/device/upgrade.png"))
        self.batch_upgrade_btn.setIconSize(QSize(16, 16))
        self.batch_upgrade_btn.setFixedSize(100, 28)
        self.batch_upgrade_btn.setEnabled(False)
        self.batch_upgrade_btn.clicked.connect(self.on_batch_upgrade)
        
        # 提示文本
        result_tip = QLabel("提示: 双击单元格可复制内容，右击设备行展开操作")
        result_tip.setStyleSheet("color: #909090; font-size: 11px; border: none;")
        
        batch_layout.addWidget(self.select_all_checkbox)
        batch_layout.addWidget(self.batch_wake_btn)
        batch_layout.addWidget(self.batch_reboot_btn)
        batch_layout.addWidget(self.batch_upgrade_btn)
        batch_layout.addStretch()
        batch_layout.addWidget(result_tip)  # 添加提示到右侧
        group_layout.addWidget(batch_frame)

        # ===== 结果表格 =====
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(10)  # 减少一列：去掉操作列
        self.result_table.setHorizontalHeaderLabels(
            ["选择", "设备名称", "型号", "SN", "ID", "密码", "接入节点", "版本号", "在线状态", "最后心跳"]
        )
        self.result_table.setFocusPolicy(Qt.StrongFocus)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)  # 改为选择整行
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setShowGrid(True)
        self.result_table.setFrameShape(QTableWidget.NoFrame)
        StyleManager.apply_to_widget(self.result_table, "TABLE")
        
        # 启用右键菜单
        self.result_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.result_table.customContextMenuRequested.connect(self.on_context_menu)
        
        # 设置列宽
        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(50)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        for col in range(1, 10):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        # 设置初始列宽（根据内容调整）
        self.result_table.setColumnWidth(0, 50)   # 选择
        self.result_table.setColumnWidth(1, 100)  # 设备名称
        self.result_table.setColumnWidth(2, 80)   # 型号
        self.result_table.setColumnWidth(3, 140)  # SN
        self.result_table.setColumnWidth(4, 100)  # ID
        self.result_table.setColumnWidth(5, 80)   # 密码
        self.result_table.setColumnWidth(6, 80)   # 接入节点
        self.result_table.setColumnWidth(7, 100)  # 版本号
        self.result_table.setColumnWidth(8, 80)   # 在线状态
        self.result_table.setColumnWidth(9, 150)  # 最后心跳（加宽以显示完整日期时间）
        
        # 初始化列宽比例
        self.column_width_ratios = {
            1: 100, 2: 80, 3: 140, 4: 100, 5: 80,
            6: 80, 7: 100, 8: 80, 9: 150
        }
        
        # 连接列宽变化事件
        header.sectionResized.connect(self.on_column_resized)
        
        # 连接双击复制事件
        self.result_table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # 连接单击事件
        self.result_table.cellClicked.connect(self.on_cell_clicked)
        
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        group_layout.addWidget(self.result_table)
        
        # ===== 导出区域（带边框） =====
        export_frame = QFrame()
        export_frame.setFrameShape(QFrame.StyledPanel)
        export_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                background-color: transparent;
            }
        """)
        export_frame.setFixedHeight(44)  # 设置固定高度，与其他区域保持一致
        export_layout = QHBoxLayout(export_frame)
        export_layout.setContentsMargins(8, 8, 8, 8)
        export_layout.setSpacing(10)
        
        export_label = QLabel("保存位置:")
        export_label.setFixedWidth(60)
        export_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        export_label.setStyleSheet("border: none;")  # 去掉边框
        
        self.export_path_input = ClickableLineEdit()
        self.export_path_input.setPlaceholderText("点击导出按钮选择保存位置（双击可打开目录）...")
        self.export_path_input.setReadOnly(True)
        self.export_path_input.setFocusPolicy(Qt.NoFocus)
        self.export_path_input.setFixedHeight(28)
        self.export_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 4px;
            }
        """)
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.setFixedSize(90, 28)
        self.export_btn.clicked.connect(self.on_export_csv)
        
        export_layout.addWidget(export_label)
        export_layout.addWidget(self.export_path_input, 1)
        export_layout.addWidget(self.export_btn)
        group_layout.addWidget(export_frame)
        
        # 创建按钮组
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(
            self.query_btn, self.clear_btn, self.phone_query_btn, self.batch_wake_btn,
            self.batch_reboot_btn, self.batch_upgrade_btn, self.select_all_checkbox, self.export_btn
        )
        
        return group

    def create_status_item(self, text, color):
        """创建状态项，颜色不受选中状态影响"""
        item = QTableWidgetItem(text)
        # 使用 setData 设置前景色，这样选中时颜色不会改变
        item.setData(Qt.ForegroundRole, QColor(color) if isinstance(color, str) else color)
        return item
    
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
        if logicalIndex == 0:
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
        fixed_width = 50  # 选择列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 10))
        
        # 如果总宽度不等于可用宽度，调整其他列
        if current_total != available_width:
            # 计算差值
            diff = available_width - current_total
            
            # 从其他列均匀调整
            other_cols = [col for col in range(1, 10) if col != logicalIndex]
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
        fixed_width = 50  # 选择列
        available_width = table_width - fixed_width
        
        if available_width <= 0:
            return
        
        # 计算当前内容列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(1, 10))
        
        # 如果当前总宽度不等于可用宽度，需要调整
        if current_total != available_width:
            # 计算缩放因子
            if current_total > 0:
                scale_factor = available_width / current_total
                
                # 按比例调整每列宽度
                for col in range(1, 10):
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
        # 跳过选择列
        if column == 0:
            return
        
        item = self.result_table.item(row, column)
        if item:
            text = item.text()
            if text and text not in ["查询中...", ""]:
                from PyQt5.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                
                # 选中当前行
                self.result_table.selectRow(row)
                
                self.show_success(f"已复制: {text}", 2000)
    
    def on_cell_clicked(self, row, column):
        """表格单元格单击"""
        # 跳过选择列
        if column == 0:
            # 清除选中状态
            self.result_table.clearSelection()
            return
        
        # 选中当前行
        self.result_table.selectRow(row)
    
    def on_context_menu(self, pos):
        """显示右键菜单"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        # 获取点击位置的行
        index = self.result_table.indexAt(pos)
        if not index.isValid():
            return
        
        row = index.row()
        
        # 跳过选择列
        if index.column() == 0:
            return
        
        # 获取设备信息
        if row >= self.result_table.rowCount():
            return
        
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
        sn_item = self.result_table.item(row, 3)
        id_item = self.result_table.item(row, 4)
        
        if not sn_item or not id_item:
            return
        
        sn = sn_item.text()
        dev_id = id_item.text()
        
        if not sn or not dev_id:
            return
        
        # 高亮当前行
        self.result_table.selectRow(row)
        
        # 创建右键菜单
        menu = QMenu(self.result_table)
        menu.setStyleSheet("""
            QMenu {
                min-width: 120px;
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #555555;
                padding: 2px;
            }
            QMenu::item {
                padding: 6px 30px 6px 6px;
                margin: 1px 2px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #505050;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #555555;
                margin: 3px 5px;
            }
        """)
        
        # 唤醒操作
        wake_action = QAction(QIcon(":/icons/device/werk_up_all.png"), "唤醒设备", self)
        wake_action.triggered.connect(lambda: self.on_wake_single(row))
        menu.addAction(wake_action)
        
        # 重启操作
        reboot_action = QAction(QIcon(":/icons/device/reboot.png"), "重启设备", self)
        reboot_action.triggered.connect(lambda: self.on_reboot_single(row))
        menu.addAction(reboot_action)
        
        # 升级操作
        upgrade_action = QAction(QIcon(":/icons/device/upgrade.png"), "升级设备", self)
        upgrade_action.triggered.connect(lambda: self.on_upgrade_single(row))
        menu.addAction(upgrade_action)
        
        # 端口穿透操作
        port_mapping_action = QAction(QIcon(":/icons/device/nat.png"), "端口穿透", self)
        port_mapping_action.triggered.connect(lambda: self.on_port_mapping_single(row))
        menu.addAction(port_mapping_action)
        
        # 显示菜单
        menu.exec_(self.result_table.viewport().mapToGlobal(pos))
    
    def on_reboot_single(self, row):
        """单个设备重启"""
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
        sn = self.result_table.item(row, 3).text()
        dev_id = self.result_table.item(row, 4).text()
        
        if not sn or not dev_id:
            self.show_warning("设备信息不完整，无法重启")
            return
        
        # 获取 DeviceQuery 对象
        env, username, password = get_account_config()
        device_query = self.ensure_device_query(env, username, password)
        
        if device_query.init_error:
            self.show_error(device_query.init_error)
            return
        
        # 显示重启对话框
        from query_tool.widgets import RebootDialog
        dialog = RebootDialog(sn, dev_id, device_query, self)
        dialog.exec_()
    
    def on_upgrade_single(self, row):
        """单个设备升级"""
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
        device_name = self.result_table.item(row, 1).text()
        model = self.result_table.item(row, 2).text()
        sn = self.result_table.item(row, 3).text()
        dev_id = self.result_table.item(row, 4).text()
        
        if not sn or not dev_id or not model:
            self.show_warning("设备信息不完整，无法升级")
            return
        
        # 获取 DeviceQuery 对象
        env, username, password = get_account_config()
        device_query = self.ensure_device_query(env, username, password)
        
        if device_query.init_error:
            self.show_error(device_query.init_error)
            return
        
        # 显示升级对话框
        from query_tool.widgets import UpgradeDialog
        dialog = UpgradeDialog(sn, dev_id, device_name, model, device_query, self)
        dialog.exec_()
    
    def on_port_mapping_single(self, row):
        """单个设备端口穿透"""
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
        device_name = self.result_table.item(row, 1).text()
        sn = self.result_table.item(row, 3).text()
        dev_id = self.result_table.item(row, 4).text()
        
        if not sn or not dev_id:
            self.show_warning("设备信息不完整，无法进行端口穿透")
            return
        
        # 获取 DeviceQuery 对象
        env, username, password = get_account_config()
        device_query = self.ensure_device_query(env, username, password)
        
        if device_query.init_error:
            self.show_error(device_query.init_error)
            return
        
        # 显示端口穿透对话框
        from query_tool.widgets import PortMappingDialog
        dialog = PortMappingDialog(sn, dev_id, device_name, device_query, self)
        dialog.exec_()
    
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
            # 显示提示对话框
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('提示')
            msg_box.setText('检测到运维系统账号信息未配置，点击OK前往配置。')
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            
            # 自定义按钮图标
            ok_btn = msg_box.button(QMessageBox.Ok)
            cancel_btn = msg_box.button(QMessageBox.Cancel)
            
            if ok_btn:
                ok_btn.setText("")
                ok_btn.setIcon(QIcon(":/icons/common/ok.png"))
                ok_btn.setIconSize(QSize(20, 20))
                ok_btn.setFixedSize(60, 32)
            
            if cancel_btn:
                cancel_btn.setText("")
                cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
                cancel_btn.setIconSize(QSize(20, 20))
                cancel_btn.setFixedSize(60, 32)
            
            # 应用样式
            StyleManager.apply_to_widget(msg_box, "DIALOG")
            
            # 延迟设置深色标题栏
            from query_tool.widgets.custom_widgets import set_dark_title_bar
            QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
            
            reply = msg_box.exec_()
            
            if reply == QMessageBox.Ok:
                from query_tool.widgets import SettingsDialog
                dialog = SettingsDialog(self.window())
                # 切换到运维账号标签页
                if hasattr(dialog, 'tab_widget'):
                    dialog.tab_widget.setCurrentIndex(0)  # 索引0是运维账号
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
        
        # 清空当前数据和筛选条件
        self.result_table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)  # 取消全选
        self.sn_filter_input.clear()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("全部")
        self.model_combo.blockSignals(False)
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        self.version_combo.blockSignals(False)
        self.all_models = set()
        self.all_versions = set()
        self.filtered_results = {}
        self.match_count_label.setText("数量: 0 / 0")
        
        # 重置数据
        self.query_results = {}
        self.total_count = len(sn_list) + len(id_list)
        self.online_count = 0
        self.offline_count = 0
        
        # 禁用按钮
        self.main_buttons.disable()
        self.query_btn.setText("查询中...")
        
        # 禁用筛选控件
        self.sn_filter_input.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.version_combo.setEnabled(False)
        
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
                checkbox.stateChanged.connect(self.on_checkbox_state_changed)
                checkbox_widget = QWidget()
                checkbox_widget.setStyleSheet("background-color: transparent;")
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.result_table.setCellWidget(row, 0, checkbox_widget)
                
                # 占位
                self.result_table.setItem(row, 1, QTableWidgetItem("查询中..."))
                for col in range(2, 10):
                    self.result_table.setItem(row, col, QTableWidgetItem(""))
        
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
        model = item.get('model', '')  # 型号
        sn = item.get('sn', '')
        dev_id = item.get('id', '')
        password = item.get('password', '')
        node = item.get('node', '')
        version = item.get('version', '')
        last_heartbeat = item.get('last_heartbeat', '')
        
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳 | 操作
        self.result_table.setItem(row, 1, QTableWidgetItem(device_name))
        self.result_table.setItem(row, 2, QTableWidgetItem(model))
        self.result_table.setItem(row, 3, QTableWidgetItem(sn))
        self.result_table.setItem(row, 4, QTableWidgetItem(dev_id))
        self.result_table.setItem(row, 5, QTableWidgetItem(password))
        self.result_table.setItem(row, 6, QTableWidgetItem(str(node)))
        self.result_table.setItem(row, 7, QTableWidgetItem(version))
        
        # 在线状态
        online_status = item.get('online', -1)
        if online_status == 1:
            status_text = "在线"
            status_color = QColor(Qt.green)
            self.online_count += 1
        elif online_status == 0:
            status_text = "离线"
            status_color = QColor(Qt.red)
            self.offline_count += 1
        elif online_status == -1:
            status_text = "未找到"
            status_color = QColor(Qt.gray)
        else:
            status_text = "查询失败"
            status_color = QColor(Qt.darkYellow)
        
        status_item = self.create_status_item(status_text, status_color)
        self.result_table.setItem(row, 8, status_item)
        
        # 最后心跳
        self.result_table.setItem(row, 9, QTableWidgetItem(last_heartbeat))
    
    def on_query_error(self, error_msg):
        """查询出错"""
        self.main_buttons.enable()
        
        # 启用筛选控件
        self.sn_filter_input.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.version_combo.setEnabled(True)
        
        self.show_error(f"查询失败: {error_msg}")
    
    def on_query_complete(self):
        """查询完成"""
        self.main_buttons.enable()
        
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
        
        # 查询完成后启用全选框，但批量操作按钮保持禁用（直到有设备被选中）
        if self.result_table.rowCount() > 0:
            self.select_all_checkbox.setEnabled(True)
        else:
            self.select_all_checkbox.setEnabled(False)
        
        # 批量操作按钮初始状态为禁用，等待用户勾选设备
        self.batch_wake_btn.setEnabled(False)
        self.batch_reboot_btn.setEnabled(False)
        self.batch_upgrade_btn.setEnabled(False)
        
        # 收集所有型号和版本号并更新下拉框
        self.update_filter_combos()
        
        # 启用筛选控件
        self.sn_filter_input.setEnabled(True)
        if len(self.all_models) > 0:
            self.model_combo.setEnabled(True)
        if len(self.all_versions) > 0:
            self.version_combo.setEnabled(True)
        
        # 初始化匹配数量为全部数量
        self.match_count_label.setText(f"数量: {self.result_table.rowCount()} / {self.total_count}")

    def on_clear(self):
        """清空按钮点击"""
        self.sn_input.clear()
        self.id_input.clear()
        self.result_table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        self.query_input_type = None
        self.query_input_list = []
        self.query_results = {}
        
        # 清空后禁用全选框和批量操作按钮
        self.select_all_checkbox.setEnabled(False)
        self.batch_wake_btn.setEnabled(False)
        self.batch_reboot_btn.setEnabled(False)
        self.batch_upgrade_btn.setEnabled(False)
        
        # 重置筛选条件
        self.sn_filter_input.clear()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("全部")
        self.model_combo.setEnabled(False)
        self.model_combo.blockSignals(False)
        
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        self.version_combo.setEnabled(False)
        self.version_combo.blockSignals(False)
        
        self.all_models = set()
        self.all_versions = set()
        self.current_sn_filter = ""
        self.current_model_filter = None
        self.current_version_filter = None
        self.filtered_results = {}
        
        # 重置匹配数量
        self.match_count_label.setText("数量: 0 / 0")
        
        # 重置原始文本和列表
        self.original_sn_text = ""
        self.original_id_text = ""
        self.original_sn_list = []
        self.original_id_list = []
        
        self.show_success("清空完成")
    
    def on_select_all(self, state):
        """全选/取消全选"""
        # 阻止所有复选框的信号，避免每个复选框变化都触发 on_checkbox_state_changed
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(state == Qt.Checked)
                checkbox.blockSignals(False)
        
        # 只在最后更新一次批量唤醒按钮状态
        self.update_batch_wake_button_state()
    
    def on_checkbox_state_changed(self):
        """单个复选框状态改变"""
        # 更新批量唤醒按钮状态
        self.update_batch_wake_button_state()
        
        # 检查是否所有复选框都被选中，更新全选框状态
        total_rows = self.result_table.rowCount()
        if total_rows == 0:
            return
        
        checked_count = 0
        for row in range(total_rows):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                checked_count += 1
        
        # 阻止信号，避免触发 on_select_all
        self.select_all_checkbox.blockSignals(True)
        if checked_count == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif checked_count == total_rows:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)
        self.select_all_checkbox.blockSignals(False)
    
    def update_batch_wake_button_state(self):
        """更新批量操作按钮状态"""
        # 检查是否有任何设备被选中
        has_checked = False
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                has_checked = True
                break
        
        self.batch_wake_btn.setEnabled(has_checked)
        self.batch_reboot_btn.setEnabled(has_checked)
        self.batch_upgrade_btn.setEnabled(has_checked)
    
    def on_wake_single(self, row):
        """单个设备唤醒"""
        # 获取原始行号
        original_row = self.display_row_to_original.get(row, row)
        
        # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
        sn = self.result_table.item(row, 3).text()
        dev_id = self.result_table.item(row, 4).text()
        
        if not sn or not dev_id:
            self.show_warning("设备信息不完整，无法唤醒")
            return
        
        self.result_table.clearSelection()
        
        # 在在线状态列显示"唤醒中..."
        status_item = self.create_status_item("唤醒中...", "#FFA500")
        self.result_table.setItem(row, 8, status_item)
        
        # 显示开始唤醒的提示
        self.show_progress(f"正在唤醒 {sn}...")
        
        # 唤醒
        try:
            env, username, password = get_account_config()
            # 使用缓存的 DeviceQuery 对象
            query = self.ensure_device_query(env, username, password)
            if query.init_error:
                # 恢复状态显示
                status_item = self.create_status_item("查询失败", QColor(Qt.darkYellow))
                self.result_table.setItem(row, 8, status_item)
                self.show_error(query.init_error)
                return
            
            # 使用唯一的线程键名，避免多个唤醒任务互相覆盖
            thread_key = f"wake_single_{row}_{dev_id}"
            wake_thread = WakeThread([(dev_id, sn)], query, max_workers=1)
            wake_thread.wake_result.connect(lambda name, success, r=row, s=sn: self.on_single_wake_done(r, s, success))
            wake_thread.finished.connect(lambda key=thread_key: self.thread_mgr.cleanup(key))
            self.thread_mgr.add(thread_key, wake_thread)
            wake_thread.start()
        except Exception as e:
            # 恢复状态显示
            status_item = self.create_status_item("唤醒失败", QColor(Qt.red))
            self.result_table.setItem(row, 8, status_item)
            self.show_error(f"唤醒失败: {str(e)}")
    
    def on_single_wake_done(self, row, sn, success):
        """单个唤醒完成"""
        if success:
            try:
                env, username, password = get_account_config()
                # 使用缓存的 DeviceQuery 对象
                query = self.ensure_device_query(env, username, password)
                if not query.init_error:
                    is_online = check_device_online(sn, query.token)
                    status_text = "在线" if is_online else "离线"
                    status_color = QColor(Qt.green) if is_online else QColor(Qt.red)
                    
                    status_item = self.create_status_item(status_text, status_color)
                    self.result_table.setItem(row, 8, status_item)
                else:
                    # 查询失败，显示未知状态
                    status_item = self.create_status_item("未知", QColor(Qt.gray))
                    self.result_table.setItem(row, 8, status_item)
            except Exception as e:
                # 查询失败，显示未知状态
                status_item = self.create_status_item("未知", QColor(Qt.gray))
                self.result_table.setItem(row, 8, status_item)
        else:
            # 唤醒失败，显示离线
            status_item = self.create_status_item("离线", QColor(Qt.red))
            self.result_table.setItem(row, 8, status_item)
        
        # 唤醒完成后，重新统计在线离线数量并显示
        self.update_device_status_summary()

    def on_batch_wake(self):
        """批量唤醒"""
        selected_devices = []
        selected_rows = []
        sn_to_row_map = {}  # 创建SN到行号的映射
        
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
                sn = self.result_table.item(row, 3).text()
                dev_id = self.result_table.item(row, 4).text()
                if sn and dev_id:
                    selected_devices.append((dev_id, sn))
                    selected_rows.append(row)
                    sn_to_row_map[sn] = row  # 保存SN到行号的映射
        
        if not selected_devices:
            self.show_warning("请先选择要唤醒的设备")
            return
        
        # 保存映射到实例变量，供回调使用
        self._batch_wake_sn_to_row = sn_to_row_map
        
        # 禁用按钮
        self.main_buttons.disable()
        self.batch_wake_btn.setText("唤醒中...")
        
        # 禁用所有复选框
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setEnabled(False)
        
        # 在在线状态列显示"唤醒中..."
        for row in selected_rows:
            status_item = self.create_status_item("唤醒中...", "#FFA500")
            self.result_table.setItem(row, 8, status_item)
        
        # 启动唤醒线程
        try:
            env, username, password = get_account_config()
            
            # 使用缓存的 DeviceQuery 对象
            query = self.ensure_device_query(env, username, password)
            
            if query.init_error:
                self.main_buttons.enable()
                # 重新启用所有复选框
                for row in range(self.result_table.rowCount()):
                    checkbox_widget = self.result_table.cellWidget(row, 0)
                    checkbox = checkbox_widget.findChild(QCheckBox)
                    if checkbox:
                        checkbox.setEnabled(True)
                # 恢复状态显示
                for row in selected_rows:
                    status_item = self.create_status_item("未知", QColor(Qt.gray))
                    self.result_table.setItem(row, 8, status_item)
                self.show_error(query.init_error)
                return
            
            wake_thread = WakeThread(selected_devices, query, max_workers=self.thread_count)
            wake_thread.wake_result.connect(self.on_wake_result)
            wake_thread.all_done.connect(lambda: self.on_wake_complete(selected_rows))
            wake_thread.progress.connect(lambda msg: self.show_progress(msg))
            wake_thread.error.connect(lambda msg: self.on_batch_wake_error(msg, selected_rows))
            
            self.thread_mgr.add("wake", wake_thread)
            wake_thread.start()
        except Exception as e:
            self.main_buttons.enable()
            # 重新启用所有复选框
            for row in range(self.result_table.rowCount()):
                checkbox_widget = self.result_table.cellWidget(row, 0)
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setEnabled(True)
            # 恢复状态显示
            for row in selected_rows:
                status_item = self.create_status_item("未知", QColor(Qt.gray))
                self.result_table.setItem(row, 8, status_item)
            self.show_error(f"初始化失败: {str(e)}")
    
    def on_wake_result(self, device_name, success):
        """唤醒结果"""
        # device_name 格式为 "SN(dev_id)"，提取SN
        # 例如: "ABC123(12345)" -> "ABC123"
        sn = device_name.split('(')[0] if '(' in device_name else device_name
        
        # 使用映射查找对应的行号
        row = None
        if hasattr(self, '_batch_wake_sn_to_row') and sn in self._batch_wake_sn_to_row:
            row = self._batch_wake_sn_to_row[sn]
        
        if row is None:
            # 如果映射不存在（单个唤醒的情况），遍历查找
            for r in range(self.result_table.rowCount()):
                item = self.result_table.item(r, 3)
                if item and item.text() == sn:
                    row = r
                    break
        
        if row is not None:
            try:
                env, username, password = get_account_config()
                # 使用缓存的 DeviceQuery 对象
                query = self.ensure_device_query(env, username, password)
                if not query.init_error:
                    is_online = check_device_online(sn, query.token)
                    status_text = "在线" if is_online else "离线"
                    status_color = QColor(Qt.green) if is_online else QColor(Qt.red)
                    
                    status_item = self.create_status_item(status_text, status_color)
                    self.result_table.setItem(row, 8, status_item)
                else:
                    # 查询失败，显示未知状态
                    status_item = self.create_status_item("未知", QColor(Qt.gray))
                    self.result_table.setItem(row, 8, status_item)
            except Exception as e:
                # 查询失败，显示未知状态
                status_item = self.create_status_item("未知", QColor(Qt.gray))
                self.result_table.setItem(row, 8, status_item)
    
    def on_wake_complete(self, selected_rows):
        """唤醒完成"""
        self.main_buttons.enable()
        
        # 启用所有复选框
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setEnabled(True)
        
        # 清理批量唤醒的映射
        if hasattr(self, '_batch_wake_sn_to_row'):
            delattr(self, '_batch_wake_sn_to_row')
        
        # 唤醒完成后，重新统计在线离线数量并显示
        self.update_device_status_summary()
    
    def on_batch_wake_error(self, error_msg, selected_rows):
        """批量唤醒出错"""
        self.main_buttons.enable()
        
        # 启用所有复选框
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setEnabled(True)
        
        self.show_error(f"唤醒失败: {error_msg}")
    
    def on_batch_reboot(self):
        """批量重启"""
        # 获取所有选中的设备
        selected_devices = []
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
                device_name = self.result_table.item(row, 1).text()
                sn = self.result_table.item(row, 3).text()
                dev_id = self.result_table.item(row, 4).text()
                if sn and dev_id:
                    selected_devices.append((sn, dev_id, device_name))
        
        if not selected_devices:
            self.show_warning("请先选择要重启的设备")
            return
        
        # 获取 DeviceQuery 对象
        env, username, password = get_account_config()
        device_query = self.ensure_device_query(env, username, password)
        
        if device_query.init_error:
            self.show_error(device_query.init_error)
            return
        
        # 显示批量重启对话框
        from query_tool.widgets import BatchRebootDialog
        dialog = BatchRebootDialog(selected_devices, device_query, self.thread_count, self)
        if dialog.exec_():
            # 对话框关闭后，刷新选中设备的在线状态
            self.refresh_selected_devices_status(selected_devices)
    
    def refresh_selected_devices_status(self, devices):
        """刷新选中设备的在线状态"""
        # 使用线程池并发查询状态
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def query_status(sn):
            try:
                env, username, password = get_account_config()
                query = self.ensure_device_query(env, username, password)
                if not query.init_error:
                    is_online = check_device_online(sn, query.token)
                    return sn, is_online
            except:
                pass
            return sn, None
        
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            futures = {executor.submit(query_status, sn): sn for sn, _, _ in devices}
            
            for future in as_completed(futures):
                sn, is_online = future.result()
                if is_online is not None:
                    # 更新表格中的状态
                    for row in range(self.result_table.rowCount()):
                        sn_item = self.result_table.item(row, 3)
                        if sn_item and sn_item.text() == sn:
                            status_text = "在线" if is_online else "离线"
                            status_color = QColor(Qt.green) if is_online else QColor(Qt.red)
                            status_item = self.create_status_item(status_text, status_color)
                            self.result_table.setItem(row, 8, status_item)
                            break
    
    def on_batch_upgrade(self):
        """批量升级"""
        # 获取所有选中的设备
        selected_devices = []
        for row in range(self.result_table.rowCount()):
            checkbox_widget = self.result_table.cellWidget(row, 0)
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
                device_name = self.result_table.item(row, 1).text()
                model = self.result_table.item(row, 2).text()
                sn = self.result_table.item(row, 3).text()
                dev_id = self.result_table.item(row, 4).text()
                if sn and dev_id and model:
                    selected_devices.append((sn, dev_id, device_name, model))
        
        if not selected_devices:
            self.show_warning("请先选择要升级的设备")
            return
        
        # 检查设备型号是否一致
        models = set(model for _, _, _, model in selected_devices)
        if len(models) > 1:
            self.show_error("所选设备型号不一致，无法进行批量升级。请筛选相同型号的设备后再试。")
            return
        
        # 获取 DeviceQuery 对象
        env, username, password = get_account_config()
        device_query = self.ensure_device_query(env, username, password)
        
        if device_query.init_error:
            self.show_error(device_query.init_error)
            return
        
        # 显示批量升级对话框
        from query_tool.widgets import BatchUpgradeDialog
        dialog = BatchUpgradeDialog(selected_devices, device_query, self.thread_count, self)
        if dialog.exec_():
            # 对话框关闭后，刷新选中设备的在线状态
            self.refresh_selected_devices_status([(sn, dev_id, name) for sn, dev_id, name, _ in selected_devices])


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
            status_item = self.result_table.item(row, 8)
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
            status_item = self.result_table.item(row, 8)
            if status_item:
                status_text = status_item.text()
                if status_text == "在线":
                    online += 1
                elif status_text == "离线":
                    offline += 1
        
        # 显示过滤后的统计信息
        self.show_success(f"筛选完成：共 {total} 台设备，在线 {online} 台，离线 {offline} 台")
    
    def refresh_table_display(self):
        """刷新表格显示"""
        # 确定要显示的数据
        display_data = self.filtered_results if self.filtered_results else self.query_results
        
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
            checkbox.stateChanged.connect(self.on_checkbox_state_changed)
            checkbox_widget = QWidget()
            checkbox_widget.setStyleSheet("background-color: transparent;")
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(display_row, 0, checkbox_widget)
            
            # 数据
            device_name = item.get('device_name', '')
            model = item.get('model', '')  # 型号
            sn = item.get('sn', '')
            dev_id = item.get('id', '')
            password = item.get('password', '')
            node = item.get('node', '')
            version = item.get('version', '')
            last_heartbeat = item.get('last_heartbeat', '')
            
            # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
            self.result_table.setItem(display_row, 1, QTableWidgetItem(device_name))
            self.result_table.setItem(display_row, 2, QTableWidgetItem(model))
            self.result_table.setItem(display_row, 3, QTableWidgetItem(sn))
            self.result_table.setItem(display_row, 4, QTableWidgetItem(dev_id))
            self.result_table.setItem(display_row, 5, QTableWidgetItem(password))
            self.result_table.setItem(display_row, 6, QTableWidgetItem(str(node)))
            self.result_table.setItem(display_row, 7, QTableWidgetItem(version))
            
            # 在线状态
            online_status = item.get('online', -1)
            if online_status == 1:
                status_text = "在线"
                status_color = QColor(Qt.green)
            elif online_status == 0:
                status_text = "离线"
                status_color = QColor(Qt.red)
            elif online_status == -1:
                status_text = "未找到"
                status_color = QColor(Qt.gray)
            else:
                status_text = "查询失败"
                status_color = QColor(Qt.darkYellow)
            
            status_item = self.create_status_item(status_text, status_color)
            self.result_table.setItem(display_row, 8, status_item)
            
            # 最后心跳
            self.result_table.setItem(display_row, 9, QTableWidgetItem(last_heartbeat))
        
        # 重新启用表格更新
        self.result_table.setUpdatesEnabled(True)
        self.result_table.viewport().update()
    
    def update_input_boxes_from_table(self):
        """根据表格内容更新输入框"""
        sn_list = []
        id_list = []
        
        for row in range(self.result_table.rowCount()):
            # 列顺序：选择 | 设备名称 | 型号 | SN | ID | 密码 | 接入节点 | 版本号 | 在线状态 | 最后心跳
            sn_item = self.result_table.item(row, 3)
            id_item = self.result_table.item(row, 4)
            
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
    
    def update_input_boxes_from_filtered_table(self):
        """根据筛选后的表格内容实时更新输入框"""
        # 检查是否有筛选条件
        sn_filter = self.sn_filter_input.text().strip().lower()
        selected_model = self.model_combo.currentText()
        selected_version = self.version_combo.currentText()
        has_filter = sn_filter or selected_model != "全部" or selected_version != "全部"
        
        # 如果没有筛选条件，恢复原始数据
        if not has_filter:
            if self.query_input_type == 'sn':
                self.sn_input.setPlainText(self.original_sn_text)
                self.id_input.setPlainText(self.original_id_text)
            elif self.query_input_type == 'id':
                self.sn_input.setPlainText(self.original_sn_text)
                self.id_input.setPlainText(self.original_id_text)
            return
        
        # 有筛选条件时，从筛选结果中提取SN和ID（可能为空）
        sn_list = []
        id_list = []
        
        for row, result in sorted(self.filtered_results.items()):
            sn = result.get('sn', '')
            dev_id = result.get('id', '')
            if sn:
                sn_list.append(sn)
            if dev_id:
                id_list.append(dev_id)
        
        # 筛选后，两个输入框都更新为筛选结果（如果没有匹配则为空）
        self.sn_input.setPlainText('\n'.join(sn_list))
        self.id_input.setPlainText('\n'.join(id_list))
    
    def load_config(self):
        """加载配置"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        if app_config.export_path:
            self.export_path = app_config.export_path
            self.export_path_input.setText(app_config.export_path)
        # 加载账号历史
        if app_config.phone_history:
            self.phone_input.addItems(app_config.phone_history)
            from PyQt5.QtWidgets import QCompleter
            completer = self.phone_input.completer()
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
    
    def save_config(self):
        """保存配置"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        app_config.export_path = self.export_path
        config_manager.save_app_config(app_config)
    
    def cleanup(self):
        """清理资源"""
        self.thread_mgr.stop_all()
    
    # ===== 账号查询相关方法 =====
    
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
        
        # 清空SN和ID文本框
        self.sn_input.clear()
        self.id_input.clear()
        
        # 清空表格和取消全选
        self.result_table.setRowCount(0)
        self.select_all_checkbox.setChecked(False)
        
        # 禁用按钮
        self.phone_query_btn.setEnabled(False)
        self.phone_query_btn.setText("查询中...")
        
        # 清空结果
        self.phone_query_results = []
        
        # 启动查询线程（使用与设备查询相同的线程数）
        phone_query_thread = PhoneQueryThread(phone, env, username, password, max_workers=self.thread_count)
        phone_query_thread.progress.connect(lambda msg: self.show_progress(msg))
        phone_query_thread.error.connect(self.on_phone_query_error)
        phone_query_thread.success.connect(self.on_phone_query_success)
        
        self.thread_mgr.add("phone_query", phone_query_thread)
        phone_query_thread.start()
    
    def on_phone_query_error(self, error_msg):
        """账号查询出错"""
        self.phone_query_btn.setEnabled(True)
        self.phone_query_btn.setText("查询账号")
        self.show_error(error_msg)
    
    def on_phone_query_success(self, results, models):
        """账号查询成功"""
        self.phone_query_results = results
        
        # 添加账号到历史
        phone = self.phone_input.currentText().strip()
        self.add_phone_to_history(phone)
        
        # 恢复按钮
        self.phone_query_btn.setEnabled(True)
        self.phone_query_btn.setText("账号查询")
        
        if not results:
            self.show_warning("该账号暂无绑定设备")
            return
        
        # 提取SN和ID列表
        sn_list = [device.get('sn', '') for device in results if device.get('sn')]
        id_list = [device.get('id', '') for device in results if device.get('id')]
        
        # 填充到输入框
        self.sn_input.setPlainText('\n'.join(sn_list))
        self.id_input.setPlainText('\n'.join(id_list))
        
        # 设置查询类型和输入列表
        self.query_input_type = 'sn'
        self.query_input_list = sn_list
        
        # 保存查询结果到 self.query_results（使用行号作为key）
        self.query_results = {}
        for row, device in enumerate(results):
            self.query_results[row] = device
        
        # 设置总数和初始化计数
        self.total_count = len(results)
        self.online_count = 0
        self.offline_count = 0
        
        # 清空筛选条件
        self.sn_filter_input.clear()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("全部")
        self.model_combo.blockSignals(False)
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        self.version_combo.blockSignals(False)
        self.all_models = set()
        self.all_versions = set()
        self.filtered_results = {}
        
        # 保存原始SN和ID列表
        self.original_sn_list = sn_list.copy()
        self.original_id_list = id_list.copy()
        self.original_sn_text = self.sn_input.toPlainText()
        self.original_id_text = self.id_input.toPlainText()
        
        # 初始化表格
        self.on_query_init_success()
        
        # 填充每一行数据
        for row, device in enumerate(results):
            self.on_single_result(row, device)
        
        # 完成查询流程
        self.on_query_complete()
        
        self.show_success(f"账号查询完成，共找到 {len(results)} 台设备")
    
    def add_phone_to_history(self, phone):
        """添加账号到历史"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        
        if phone in app_config.phone_history:
            app_config.phone_history.remove(phone)
        
        app_config.phone_history.insert(0, phone)
        app_config.phone_history = app_config.phone_history[:5]
        
        self.phone_input.clear()
        self.phone_input.addItems(app_config.phone_history)
        
        config_manager.save_app_config(app_config)
    
    # ===== 筛选相关方法 =====
    
    def update_filter_combos(self):
        """更新型号和版本下拉框"""
        # 收集所有型号和版本号
        self.all_models = set()
        self.all_versions = set()
        
        for row, result in self.query_results.items():
            model = result.get('model', '')
            if model:
                self.all_models.add(model)
            version = result.get('version', '')
            if version:
                self.all_versions.add(version)
        
        # 更新型号下拉框
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItem("全部")
        for model in sorted(self.all_models):
            self.model_combo.addItem(model)
        self.model_combo.setEnabled(len(self.all_models) > 0)
        self.model_combo.blockSignals(False)
        
        # 更新版本下拉框
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        for version in sorted(self.all_versions):
            self.version_combo.addItem(version)
        self.version_combo.setEnabled(len(self.all_versions) > 0)
        self.version_combo.blockSignals(False)
        
        # 重置筛选
        self.current_sn_filter = ""
        self.current_model_filter = None
        self.current_version_filter = None
        self.filtered_results = {}
    
    def on_filter_changed(self):
        """筛选条件变化"""
        sender = self.sender()
        
        # 获取当前筛选条件
        sn_filter = self.sn_filter_input.text().strip().lower()
        selected_model = self.model_combo.currentText()
        selected_version = self.version_combo.currentText()
        
        # 根据触发源处理逻辑
        if sender == self.sn_filter_input:
            # SN筛选时，型号和版本自动选择"全部"
            if sn_filter:
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentText("全部")
                self.model_combo.blockSignals(False)
                
                self.version_combo.blockSignals(True)
                self.version_combo.setCurrentText("全部")
                self.version_combo.blockSignals(False)
                
                selected_model = "全部"
                selected_version = "全部"
        
        elif sender == self.model_combo:
            # 选择型号时，清空SN筛选
            if selected_model != "全部":
                self.sn_filter_input.blockSignals(True)
                self.sn_filter_input.clear()
                self.sn_filter_input.blockSignals(False)
                sn_filter = ""
            
            # 更新版本下拉框以匹配该型号的所有版本
            self.update_version_combo_by_model(selected_model)
        
        elif sender == self.version_combo:
            # 选择版本时，清空SN筛选
            if selected_version != "全部":
                self.sn_filter_input.blockSignals(True)
                self.sn_filter_input.clear()
                self.sn_filter_input.blockSignals(False)
                sn_filter = ""
        
        # 应用筛选
        self.apply_filters(sn_filter, selected_model, selected_version)
    
    def update_version_combo_by_model(self, selected_model):
        """根据型号更新版本下拉框"""
        # 获取当前选中的版本
        current_version = self.version_combo.currentText()
        
        # 阻止信号
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItem("全部")
        
        # 提取对应型号的所有版本号
        versions = set()
        
        for row, result in self.query_results.items():
            # 按型号筛选
            if selected_model != "全部":
                if result.get('model', '') != selected_model:
                    continue
            
            # 提取版本号
            version = result.get('version', '')
            if version:
                versions.add(version)
        
        # 添加版本号到下拉框
        for version in sorted(versions):
            self.version_combo.addItem(version)
        
        # 恢复之前选中的版本（如果存在）
        index = self.version_combo.findText(current_version)
        if index >= 0:
            self.version_combo.setCurrentIndex(index)
        else:
            self.version_combo.setCurrentIndex(0)
        
        self.version_combo.blockSignals(False)
    
    def apply_filters(self, sn_filter, selected_model, selected_version):
        """应用筛选条件"""
        # 检查是否有任何筛选条件
        has_filter = sn_filter or selected_model != "全部" or selected_version != "全部"
        
        # 筛选设备
        self.filtered_results = {}
        
        if has_filter:
            for row, result in self.query_results.items():
                # 按SN筛选（按位匹配，从开头匹配）
                if sn_filter:
                    sn = result.get('sn', '').lower()
                    if not sn.startswith(sn_filter):
                        continue
                
                # 按型号筛选
                if selected_model != "全部":
                    if result.get('model', '') != selected_model:
                        continue
                
                # 按版本筛选
                if selected_version != "全部":
                    if result.get('version', '') != selected_version:
                        continue
                
                self.filtered_results[row] = result
        
        # 清除全选框状态
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(False)
        self.select_all_checkbox.blockSignals(False)
        
        # 更新表格显示
        self.refresh_table_display()
        
        # 更新数量显示
        if has_filter:
            filtered_count = len(self.filtered_results)
            total_count = len(self.query_results)
            self.match_count_label.setText(f"数量: {filtered_count} / {total_count}")
        else:
            total_count = len(self.query_results)
            self.match_count_label.setText(f"数量: {total_count} / {total_count}")
        
        # 实时更新SN和ID文本框数据
        self.update_input_boxes_from_filtered_table()
        
        # 更新统计信息
        if has_filter and len(self.filtered_results) < len(self.query_results):
            self.update_filtered_status_summary()
        else:
            self.update_device_status_summary()
