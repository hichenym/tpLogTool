"""
固件查询页面
提供固件列表查询和筛选功能
"""
import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit, QComboBox,
    QFrame, QWidget, QMessageBox
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon, QColor

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import ButtonManager, ThreadManager, StyleManager, config_manager
from query_tool.widgets.custom_widgets import set_dark_title_bar
from query_tool.widgets import EditFirmwareDialog
from query_tool.utils.logger import logger

# 导入固件列表获取函数
from query_tool.utils.firmware_api import login, fetch_firmware_data, parse_firmware_data, delete_firmware, get_firmware_detail, update_firmware


class NoWheelComboBox(QComboBox):
    """禁用鼠标滚轮切换的下拉框"""
    def wheelEvent(self, event):
        """禁用鼠标滚轮事件"""
        event.ignore()


class FirmwareQueryThread(QThread):
    """固件查询后台线程"""
    finished_signal = pyqtSignal(list, int, int)  # 查询完成，返回固件列表、总条数、总页数
    error_signal = pyqtSignal(str)      # 查询错误
    progress_signal = pyqtSignal(str)   # 进度信息
    
    def __init__(self, create_user='cur', device_identify='', audit_result='', page=1, per_page=100):
        super().__init__()
        self.create_user = create_user
        self.device_identify = device_identify
        self.audit_result = audit_result
        self.page = page
        self.per_page = per_page
    
    def run(self):
        """执行查询"""
        try:
            # 发送进度信息
            self.progress_signal.emit("正在查询固件数据...")
            
            # 获取固件数据（内部会自动登录）
            result = fetch_firmware_data(
                create_user=self.create_user,
                device_identify=self.device_identify,
                audit_result=self.audit_result,
                page=self.page,
                per_page=self.per_page
            )
            
            # 检查返回值
            if result is None or len(result) != 3:
                self.error_signal.emit("获取固件数据失败：返回值格式错误")
                return
            
            firmware_list, total_count, total_pages = result
            
            if firmware_list is None:
                self.error_signal.emit("获取固件数据失败")
                return
            
            # 返回结果（包括total_count和total_pages）
            self.finished_signal.emit(firmware_list, total_count, total_pages)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_signal.emit(f"查询出错: {str(e)}")


@register_page("固件", order=2, icon=":/icons/device/firmware.png")
class FirmwarePage(BasePage):
    """固件查询页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "固件"
        
        # 管理器
        self.btn_manager = ButtonManager()
        self.thread_mgr = ThreadManager()
        
        # 数据
        self.firmware_list = []          # 原始固件列表
        self.filtered_list = []          # 筛选后的列表
        self.all_publishers = set()      # 所有发布人员
        self.is_current_user_query = False  # 是否查询的是当前用户的数据
        self.current_user_display_name = None  # 当前登录用户的显示名称
        
        # 分页相关
        self.current_page = 1            # 当前页
        self.total_pages = 1             # 总页数
        self.total_count = 0             # 总条数
        self.per_page = 100              # 每页条数
        
        # 列宽管理
        self.column_width_ratios = {}
        self.resize_timer = None
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(8)
        
        # 查询区
        query_group = self.create_query_group()
        page_layout.addWidget(query_group)
        
        # 结果区
        result_group = self.create_result_group()
        page_layout.addWidget(result_group)
        
        # 创建按钮组（包含新增、查询和重置按钮，翻页按钮单独管理）
        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(self.add_firmware_btn)
        self.main_buttons.add(self.query_btn)
        self.main_buttons.add(self.reset_btn)
    
    def create_query_group(self):
        """创建管理分组"""
        group = QGroupBox("管理")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # 创建水平布局，包含新增按钮和查询框
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)
        
        # 新增固件按钮（放在方框外面左边）
        self.add_firmware_btn = QPushButton("新增固件")
        self.add_firmware_btn.setIcon(QIcon(":/icons/common/add.png"))
        self.add_firmware_btn.setIconSize(QSize(16, 16))
        self.add_firmware_btn.setFixedHeight(44)  # 与查询框同高
        self.add_firmware_btn.setStyleSheet("QPushButton { padding-left: 8px; padding-right: 8px; }")
        self.add_firmware_btn.clicked.connect(self.on_add_firmware)
        
        top_layout.addWidget(self.add_firmware_btn)
        
        # 查询条件区（带边框）
        query_frame = QFrame()
        query_frame.setFrameShape(QFrame.StyledPanel)
        query_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #555555;
                background-color: transparent;
            }
        """)
        query_frame.setFixedHeight(44)
        query_layout = QHBoxLayout(query_frame)
        query_layout.setContentsMargins(8, 8, 8, 8)
        query_layout.setSpacing(10)
        
        # 发布人员
        publisher_label = QLabel("发布人员:")
        publisher_label.setFixedWidth(70)
        publisher_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        publisher_label.setStyleSheet("border: none;")
        
        self.publisher_combo = NoWheelComboBox()
        self.publisher_combo.setEditable(False)  # 禁止编辑，只能选择
        self.publisher_combo.setFocusPolicy(Qt.StrongFocus)
        self.publisher_combo.setFixedHeight(28)
        self.publisher_combo.addItem("当前登录用户")
        self.publisher_combo.addItem("全部")
        
        # 审核状态
        audit_label = QLabel("审核状态:")
        audit_label.setFixedWidth(70)
        audit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        audit_label.setStyleSheet("border: none;")
        
        self.audit_combo = NoWheelComboBox()
        self.audit_combo.setEditable(False)  # 禁止编辑，只能选择
        self.audit_combo.setFocusPolicy(Qt.StrongFocus)
        self.audit_combo.setFixedHeight(28)
        self.audit_combo.addItem("全部", "")  # 值为空字符串
        self.audit_combo.addItem("无需审核", "1")
        self.audit_combo.addItem("待审核", "2")
        self.audit_combo.addItem("审核通过", "3")
        self.audit_combo.addItem("审核不通过", "4")
        
        # 固件标识
        identifier_label = QLabel("固件标识:")
        identifier_label.setFixedWidth(70)
        identifier_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        identifier_label.setStyleSheet("border: none;")
        
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("输入固件标识（可为空）...")
        self.identifier_input.setFixedHeight(28)
        
        # 查询按钮
        self.query_btn = QPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedHeight(28)
        self.query_btn.setStyleSheet("QPushButton { padding-left: 8px; padding-right: 8px; }")
        self.query_btn.clicked.connect(self.on_query)
        
        # 重置按钮
        self.reset_btn = QPushButton("重置")
        self.reset_btn.setIcon(QIcon(":/icons/common/clean.png"))
        self.reset_btn.setIconSize(QSize(16, 16))
        self.reset_btn.setFixedHeight(28)
        self.reset_btn.setStyleSheet("QPushButton { padding-left: 8px; padding-right: 8px; }")
        self.reset_btn.clicked.connect(self.on_reset)
        
        query_layout.addWidget(publisher_label)
        query_layout.addWidget(self.publisher_combo, 1)
        query_layout.addSpacing(10)
        query_layout.addWidget(audit_label)
        query_layout.addWidget(self.audit_combo, 1)
        query_layout.addSpacing(10)
        query_layout.addWidget(identifier_label)
        query_layout.addWidget(self.identifier_input, 2)
        query_layout.addSpacing(10)
        query_layout.addWidget(self.query_btn)
        query_layout.addSpacing(5)
        query_layout.addWidget(self.reset_btn)
        
        top_layout.addWidget(query_frame, 1)  # 添加伸展因子，让查询框占据剩余空间
        
        group_layout.addLayout(top_layout)
        
        return group
    
    def create_result_group(self):
        """创建结果分组"""
        group = QGroupBox("结果")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 15, 10, 10)
        group_layout.setSpacing(8)
        
        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels(
            ["固件标识", "审核结果", "开始时间", "结束时间", "发布人员", "发布备注"]
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
        header.setMinimumSectionSize(80)
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        
        # 初始列宽
        self.result_table.setColumnWidth(0, 200)  # 固件标识
        self.result_table.setColumnWidth(1, 100)  # 审核结果
        self.result_table.setColumnWidth(2, 150)  # 开始时间
        self.result_table.setColumnWidth(3, 150)  # 结束时间
        self.result_table.setColumnWidth(4, 100)  # 发布人员
        self.result_table.setColumnWidth(5, 250)  # 发布备注
        
        # 初始化列宽比例
        self.column_width_ratios = {
            0: 200,
            1: 100,
            2: 150,
            3: 150,
            4: 100,
            5: 250
        }
        
        # 连接列宽变化事件
        header.sectionResized.connect(self.on_column_resized)
        
        # 连接双击复制事件
        self.result_table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        # 连接单击事件
        self.result_table.cellClicked.connect(self.on_cell_clicked)
        
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 翻页控件布局
        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 3, 0, 0)
        pagination_layout.setSpacing(3)
        
        # 上一页按钮
        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_btn.setIconSize(QSize(18, 18))
        self.prev_btn.setFixedSize(30, 22)
        self.prev_btn.setStyleSheet("QPushButton { padding: 0px; }")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.on_prev_page)
        
        # 页码标签
        self.page_label = QLabel("[0/0]")
        self.page_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self.page_label.setFixedHeight(22)
        self.page_label.setMinimumWidth(60)
        self.page_label.setAlignment(Qt.AlignCenter)
        
        # 下一页按钮
        self.next_btn = QPushButton()
        self.next_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_btn.setIconSize(QSize(18, 18))
        self.next_btn.setFixedSize(30, 22)
        self.next_btn.setStyleSheet("QPushButton { padding: 0px; }")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.on_next_page)
        
        pagination_layout.addWidget(self.prev_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_btn)
        pagination_layout.addStretch()
        
        # 提示文本
        tip_label = QLabel("提示: 双击单元格可复制内容，右击固件行展开操作")
        tip_label.setStyleSheet("color: #909090; font-size: 11px;")
        tip_label.setFixedHeight(22)
        tip_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        pagination_layout.addWidget(tip_label)
        
        group_layout.addWidget(self.result_table)
        group_layout.addLayout(pagination_layout)
        
        return group
    
    def on_page_show(self):
        """页面显示时"""
        self.show_info("固件页面")
        # 调整表格列宽以适应当前窗口
        self.adjust_table_columns()
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        self.adjust_table_columns()
    
    def on_column_resized(self, logicalIndex):
        """列宽被用户调节时，使用防抖机制延迟调整其他列"""
        # 如果已有待处理的调整，取消它
        if self.resize_timer is not None:
            self.resize_timer.stop()
        
        # 创建新的防抖计时器（200ms 延迟）
        from PyQt5.QtCore import QTimer
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda: self._do_column_resize(logicalIndex))
        self.resize_timer.start(200)
    
    def _do_column_resize(self, logicalIndex):
        """实际执行列宽调整"""
        # 获取表格可用宽度
        table_width = self.result_table.width()
        available_width = table_width
        
        if available_width <= 0:
            return
        
        # 计算当前所有列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(6))
        
        # 如果总宽度不等于可用宽度，调整其他列
        if current_total != available_width:
            # 计算差值
            diff = available_width - current_total
            
            # 从其他列均匀调整
            other_cols = [col for col in range(6) if col != logicalIndex]
            if other_cols:
                adjustment_per_col = diff / len(other_cols)
                for col in other_cols:
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(80, int(current_width + adjustment_per_col))
                    self.result_table.setColumnWidth(col, new_width)
        
        # 更新该列的比例
        new_width = self.result_table.columnWidth(logicalIndex)
        if logicalIndex in self.column_width_ratios:
            self.column_width_ratios[logicalIndex] = new_width
    
    def adjust_table_columns(self):
        """根据窗口宽度调整表格列宽，保持表格宽度与窗口一致"""
        # 获取表格可用宽度
        table_width = self.result_table.width()
        available_width = table_width
        
        if available_width <= 0:
            return
        
        # 计算当前所有列的总宽度
        current_total = sum(self.result_table.columnWidth(col) for col in range(6))
        
        # 如果当前总宽度不等于可用宽度，需要调整
        if current_total != available_width:
            # 计算缩放因子
            if current_total > 0:
                scale_factor = available_width / current_total
                
                # 按比例调整每列宽度
                for col in range(6):
                    current_width = self.result_table.columnWidth(col)
                    new_width = max(80, int(current_width * scale_factor))
                    self.result_table.setColumnWidth(col, new_width)
    
    def get_current_user_display_name(self):
        """获取当前登录用户的显示名称"""
        if self.current_user_display_name:
            return self.current_user_display_name
        
        # 如果还没有获取到，尝试从固件列表中获取
        # 当查询当前用户时，所有记录的发布人员都是当前用户
        if self.is_current_user_query and self.firmware_list:
            first_publisher = self.firmware_list[0].get('publisher', '')
            if first_publisher:
                self.current_user_display_name = first_publisher
                return first_publisher
        
        # 如果还是没有，返回一个默认值（不应该发生）
        return "未知用户"
    
    def on_add_firmware(self):
        """新增固件按钮点击"""
        # 检查固件账号是否配置
        from query_tool.utils.config import get_firmware_account_config
        firmware_username, firmware_password = get_firmware_account_config()
        
        if not firmware_username or not firmware_password:
            # 显示提示对话框
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('需要配置固件账号')
            msg_box.setText('检测到固件账号未配置，是否现在配置？')
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            
            # 自定义按钮图标
            yes_btn = msg_box.button(QMessageBox.Yes)
            no_btn = msg_box.button(QMessageBox.No)
            
            if yes_btn:
                yes_btn.setText("")
                yes_btn.setIcon(QIcon(":/icons/common/ok.png"))
                yes_btn.setIconSize(QSize(20, 20))
                yes_btn.setFixedSize(60, 32)
            
            if no_btn:
                no_btn.setText("")
                no_btn.setIcon(QIcon(":/icons/common/cancel.png"))
                no_btn.setIconSize(QSize(20, 20))
                no_btn.setFixedSize(60, 32)
            
            # 应用样式
            StyleManager.apply_to_widget(msg_box, "DIALOG")
            
            # 延迟设置深色标题栏
            QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
            
            reply = msg_box.exec_()
            
            if reply == QMessageBox.Yes:
                # 打开设置对话框
                self.open_settings_dialog()
            
            return
        
        self.show_progress("正在加载新增页面...")
        
        # 获取 CSRF token
        from query_tool.utils.firmware_api import login
        from bs4 import BeautifulSoup
        
        session = login()
        if not session:
            self.show_error("登录失败，无法新增固件")
            return
        
        try:
            # 访问新增页面获取 token
            create_url = "https://update.seetong.com/admin/update/debug-firmware/create"
            response = session.get(create_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 提取 CSRF token
                token_meta = soup.find('meta', {'name': 'csrf-token'})
                if token_meta:
                    csrf_token = token_meta.get('content', '')
                else:
                    # 从 input 获取
                    token_inputs = soup.find_all('input', {'name': '_token'})
                    csrf_token = ''
                    for token_input in token_inputs:
                        token_value = token_input.get('value', '')
                        if token_value and '{{' not in token_value and 'csrf_token()' not in token_value:
                            csrf_token = token_value
                            break
                
                if csrf_token:
                    # 获取当天的开始和结束时间
                    from datetime import datetime
                    today = datetime.now()
                    start_time_str = today.strftime('%Y-%m-%d 00:00:00')
                    end_time_str = today.strftime('%Y-%m-%d 23:59:59')
                    
                    # 创建空的固件数据
                    firmware_data = {
                        '_token': csrf_token,
                        'device_identify': '',
                        'file_md5': '',
                        'create_comment': '',
                        'support_sn': '',
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'file_temp_path': '',
                        'file_formal_path': '',
                        'file_url': '',
                        'file_path': '',
                        'model_id': '',
                        'version_info': '',
                        'audit_result': '1',
                        'audit_user_id': '',
                        'audit_remark': '',
                        'audit_time': ''
                    }
                    
                    self.show_info("加载完成")
                    
                    # 显示新增对话框（firmware_id 为 None 表示新增模式）
                    dialog = EditFirmwareDialog(None, firmware_data, self)
                    
                    result = dialog.exec_()
                    if result == EditFirmwareDialog.Accepted:
                        result_data = dialog.get_result()
                        if result_data:
                            self.submit_firmware_create(result_data)
                    else:
                        # 用户取消了新增
                        self.show_info("已取消新增固件")
                else:
                    self.show_error("无法获取 CSRF token")
            else:
                self.show_error(f"加载新增页面失败: HTTP {response.status_code}")
        except Exception as e:
            self.show_error(f"加载新增页面出错: {str(e)}")
    
    def submit_firmware_create(self, data):
        """提交新增固件"""
        identifier = data.get('device_identify', '未知')
        self.show_progress(f"正在新增固件: {identifier}...")
        
        # 在后台线程中提交
        from PyQt5.QtCore import QThread, pyqtSignal
        from query_tool.utils.firmware_api import login
        
        class CreateThread(QThread):
            finished_signal = pyqtSignal(bool, str)
            
            def __init__(self, data):
                super().__init__()
                self.data = data
            
            def run(self):
                try:
                    session = login()
                    if not session:
                        self.finished_signal.emit(False, "登录失败")
                        return
                    
                    # 新增接口
                    create_url = "https://update.seetong.com/admin/update/debug-firmware"
                    
                    # 设置请求头
                    headers = {
                        'Accept': 'text/html, */*; q=0.01',
                        'Accept-Language': 'zh-CN,zh;q=0.9',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-PJAX': 'true',
                        'X-PJAX-Container': '#pjax-container',
                        'Referer': 'https://update.seetong.com/admin/update/debug-firmware/create',
                        'Origin': 'https://update.seetong.com'
                    }
                    
                    # 发送 POST 请求
                    response = session.post(create_url, data=self.data, headers=headers, allow_redirects=True)
                    
                    if response.status_code == 200:
                        # 检查是否重定向到列表页
                        if 'debug-firmware' in response.url and 'create' not in response.url:
                            self.finished_signal.emit(True, "新增成功")
                        else:
                            # 检查错误信息
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(response.text, 'html.parser')
                            error_alert = soup.find('div', class_='alert-danger')
                            if error_alert:
                                error_msg = error_alert.get_text(strip=True)
                                self.finished_signal.emit(False, error_msg)
                            else:
                                self.finished_signal.emit(True, "新增成功")
                    else:
                        self.finished_signal.emit(False, f"HTTP {response.status_code}")
                except Exception as e:
                    self.finished_signal.emit(False, str(e))
        
        create_thread = CreateThread(data)
        create_thread.finished_signal.connect(lambda success, msg: self.on_create_finished(success, msg, identifier))
        create_thread.finished.connect(lambda: create_thread.deleteLater())
        self.thread_mgr.add("create", create_thread)
        create_thread.start()
        
        # 保存线程引用
        self._create_thread = create_thread
    
    def on_create_finished(self, success, message, identifier):
        """新增完成回调"""
        if success:
            self.show_success(f"新增成功: {identifier}")
            # 刷新列表（回到第1页）
            self.current_page = 1
            self.query_with_page(self.current_page)
        else:
            self.show_error(f"新增失败: {message}")
    
    def on_query(self):
        """查询按钮点击"""
        # 重置为第1页
        self.current_page = 1
        self.total_pages = 1  # 重置总页数
        self.query_with_page(self.current_page)
    
    def on_reset(self):
        """重置按钮点击"""
        # 重置查询条件为默认值
        self.publisher_combo.setCurrentIndex(0)  # 默认选择"当前登录用户"
        self.audit_combo.setCurrentIndex(0)      # 默认选择"全部"
        self.identifier_input.clear()            # 清空固件标识输入框
        
        # 清空查询结果
        self.firmware_list = []
        self.filtered_list = []
        self.all_publishers = set()
        self.is_current_user_query = False
        self.current_user_display_name = None
        
        # 清空表格
        self.result_table.setRowCount(0)
        
        # 重置分页
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self.update_pagination()
        
        # 显示提示
        self.show_info("已重置查询条件和结果")
    
    def query_with_page(self, page):
        """带分页参数的查询"""
        # 检查固件账号是否配置
        from query_tool.utils.config import get_firmware_account_config
        firmware_username, firmware_password = get_firmware_account_config()
        
        if not firmware_username or not firmware_password:
            # 显示提示对话框
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('需要配置固件账号')
            msg_box.setText('检测到固件账号未配置，是否现在配置？')
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            
            # 自定义按钮图标
            yes_btn = msg_box.button(QMessageBox.Yes)
            no_btn = msg_box.button(QMessageBox.No)
            
            if yes_btn:
                yes_btn.setText("")
                yes_btn.setIcon(QIcon(":/icons/common/ok.png"))
                yes_btn.setIconSize(QSize(20, 20))
                yes_btn.setFixedSize(60, 32)
            
            if no_btn:
                no_btn.setText("")
                no_btn.setIcon(QIcon(":/icons/common/cancel.png"))
                no_btn.setIconSize(QSize(20, 20))
                no_btn.setFixedSize(60, 32)
            
            # 应用样式
            StyleManager.apply_to_widget(msg_box, "DIALOG")
            
            # 延迟设置深色标题栏
            QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
            
            reply = msg_box.exec_()
            
            if reply == QMessageBox.Yes:
                # 打开设置对话框
                self.open_settings_dialog()
            
            return
        
        # 更新当前页码
        self.current_page = page
        
        # 获取固件标识
        device_identify = self.identifier_input.text().strip()
        
        # 获取发布人员选择
        publisher_text = self.publisher_combo.currentText()
        
        # 根据选择确定create_user参数
        if publisher_text == "全部":
            create_user = 'all'
            query_desc = "全部用户"
            self.is_current_user_query = False
        else:
            create_user = 'cur'
            query_desc = "当前登录用户"
            self.is_current_user_query = True  # 标记为当前用户查询
        
        # 获取审核状态
        audit_result = self.audit_combo.currentData()  # 获取关联的值
        
        # 构建查询描述
        if device_identify:
            query_desc = f"{query_desc}，固件标识: {device_identify}"
        if audit_result:
            audit_text = self.audit_combo.currentText()
            query_desc = f"{query_desc}，审核状态: {audit_text}"
        
        self.show_progress(f"正在查询固件列表（{query_desc}，第{page}页）...")
        
        # 禁用所有按钮
        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        
        # 清空当前数据
        self.result_table.setRowCount(0)
        
        # 清理旧的查询线程（更健壮的检查，避免访问已被删除的 C++ 对象）
        if hasattr(self, '_query_thread') and self._query_thread:
            try:
                # 有时底层 C++ 对象已被 deleteLater 删除，调用方法会抛出 RuntimeError
                # 先检查 isRunning 并在 try/except 中安全调用 quit()/wait()
                is_running = False
                try:
                    is_running = bool(self._query_thread.isRunning())
                except RuntimeError:
                    # 对象已被删除，直接清理引用
                    from query_tool.utils.logger import logger
                    logger.debug("清理查询线程时发现对象已被删除")
                    self._query_thread = None
                    is_running = False

                if is_running:
                    try:
                        self._query_thread.quit()
                        self._query_thread.wait(timeout=2000)
                    except RuntimeError as e:
                        from query_tool.utils.logger import logger
                        logger.debug(f"清理查询线程失败（已删除）: {e}")
                    except Exception as e:
                        from query_tool.utils.logger import logger
                        logger.debug(f"清理查询线程失败: {e}")

            finally:
                # 无论如何都不要保留对已删除或已停止线程的引用
                try:
                    self._query_thread = None
                except Exception:
                    self._query_thread = None
        
        # 启动查询线程，传递create_user、device_identify、audit_result和page参数
        query_thread = FirmwareQueryThread(
            create_user=create_user,
            device_identify=device_identify,
            audit_result=audit_result,
            page=page,
            per_page=self.per_page
        )
        query_thread.finished_signal.connect(self.on_query_success)
        query_thread.error_signal.connect(self.on_query_error)
        query_thread.progress_signal.connect(lambda msg: self.show_progress(msg))
        query_thread.finished.connect(lambda: query_thread.deleteLater())
        
        # 保存线程引用
        self._query_thread = query_thread
        self.thread_mgr.add("query", query_thread)
        query_thread.start()
    
    def open_settings_dialog(self):
        """打开设置对话框"""
        from query_tool.widgets import SettingsDialog
        dialog = SettingsDialog(self.window())
        # 切换到固件账号标签页
        if hasattr(dialog, 'tab_widget'):
            dialog.tab_widget.setCurrentIndex(1)  # 索引1是固件账号
        dialog.exec_()
    
    def on_query_success(self, firmware_list, total_count, total_pages):
        """查询成功"""
        # 更新数据
        self.firmware_list = firmware_list if firmware_list else []
        self.filtered_list = self.firmware_list.copy()
        
        # 关键：先更新总页数和总条数
        self.total_count = total_count
        self.total_pages = total_pages
        
        # 提取所有发布人员
        self.all_publishers = set()
        for firmware in self.firmware_list:
            publisher = firmware.get('publisher', '')
            if publisher:
                self.all_publishers.add(publisher)
        
        # 如果是查询当前用户，记录当前用户的显示名称
        if self.is_current_user_query and self.firmware_list:
            # 从第一条记录获取当前用户的显示名称
            first_publisher = self.firmware_list[0].get('publisher', '')
            if first_publisher:
                self.current_user_display_name = first_publisher
        
        # 更新表格
        self.update_table()
        
        # 更新分页状态（使用最新的total_pages）
        self.update_pagination()
        
        # 恢复查询按钮
        self.query_btn.setEnabled(True)
        self.query_btn.setText("查询")
        
        self.show_success(f"查询成功! 共 {self.total_count} 条记录，当前第 {self.current_page}/{self.total_pages} 页")
    
    def on_query_error(self, error_msg):
        """查询失败"""
        self.query_btn.setEnabled(True)
        self.query_btn.setText("查询")
        # 恢复翻页按钮状态
        self.update_pagination()
        self.show_error(f"查询失败: {error_msg}")
    
    def update_pagination(self):
        """更新分页状态"""
        # 更新页码标签
        page_text = f"[{self.current_page}/{self.total_pages}]"
        self.page_label.setText(page_text)
        
        # 更新按钮状态
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
    
    def on_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.query_with_page(self.current_page)
    
    def on_next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.query_with_page(self.current_page)
    
    
    def update_table(self):
        """更新表格显示"""
        self.result_table.setRowCount(len(self.filtered_list))
        
        # 计算起始序号：(当前页-1) * 每页条数 + 1
        start_index = (self.current_page - 1) * self.per_page + 1
        
        # 审核结果文本映射和颜色
        audit_result_color_map = {
            '无需审核': '#909090',      # 灰色
            '待审核': '#FFA500',        # 橙色
            '审核通过': '#00FF00',      # 绿色
            '审核不通过': '#FF0000',    # 红色
        }
        
        for row, firmware in enumerate(self.filtered_list):
            # 设置行号（垂直表头）
            actual_row_number = start_index + row
            self.result_table.setVerticalHeaderItem(row, QTableWidgetItem(str(actual_row_number)))
            
            # 固件标识
            identifier = firmware.get('identifier', '')
            item = QTableWidgetItem(identifier)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # 将下载链接保存到item的data中，用于右键菜单
            download_url = firmware.get('download_url', '')
            item.setData(Qt.UserRole, download_url)
            self.result_table.setItem(row, 0, item)
            
            # 审核结果
            audit_result = firmware.get('audit_result', '未知')
            item = QTableWidgetItem(audit_result)
            item.setTextAlignment(Qt.AlignCenter)
            # 根据审核结果设置颜色（使用 setData 保持颜色不受选中状态影响）
            audit_color = audit_result_color_map.get(audit_result, '#909090')  # 默认灰色
            item.setData(Qt.ForegroundRole, QColor(audit_color))
            self.result_table.setItem(row, 1, item)
            
            # 开始时间
            start_time = firmware.get('start_time', '')
            item = QTableWidgetItem(start_time)
            item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(row, 2, item)
            
            # 结束时间
            end_time = firmware.get('end_time', '')
            item = QTableWidgetItem(end_time)
            item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(row, 3, item)
            
            # 发布人员
            publisher = firmware.get('publisher', '')
            item = QTableWidgetItem(publisher)
            item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(row, 4, item)
            
            # 发布备注
            remark = firmware.get('remark', '')
            item = QTableWidgetItem(remark)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.result_table.setItem(row, 5, item)
        
        # 调整行高以适应内容
        self.result_table.resizeRowsToContents()
    
    def on_cell_double_clicked(self, row, column):
        """表格单元格双击复制"""
        item = self.result_table.item(row, column)
        if item:
            text = item.text()
            if text:
                from PyQt5.QtWidgets import QApplication
                clipboard = QApplication.clipboard()
                clipboard.setText(text)
                
                # 选中当前行
                self.result_table.selectRow(row)
                
                self.show_success(f"已复制: {text}", 2000)
    
    def on_cell_clicked(self, row, column):
        """表格单元格单击"""
        # 选中当前行
        self.result_table.selectRow(row)
    
    def on_context_menu(self, pos):
        """显示右键菜单"""
        from PyQt5.QtWidgets import QMenu, QAction, QApplication, QMessageBox
        
        # 获取点击位置的单元格
        index = self.result_table.indexAt(pos)
        if not index.isValid():
            return
        
        row = index.row()
        
        # 获取当前行的固件信息
        if row >= len(self.filtered_list):
            return
        
        firmware = self.filtered_list[row]
        
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
        
        # 基础操作：复制下载链接
        download_url = firmware.get('download_url', '')
        if download_url:
            copy_url_action = QAction(QIcon(":/icons/common/link.png"), "复制下载链接", self)
            copy_url_action.triggered.connect(lambda: self.copy_download_url_from_data(row))
            menu.addAction(copy_url_action)
        
        # 获取发布人员和当前登录用户
        publisher = firmware.get('publisher', '')
        
        # 获取当前登录用户的显示名称
        current_user_display_name = self.get_current_user_display_name()
        
        # 判断是否有操作权限
        # 如果是查询当前用户的数据，则所有结果都可以编辑和删除
        # 如果是查询全部用户，则只有发布人员是当前用户的才能编辑和删除
        if self.is_current_user_query:
            has_edit_permission = True
            has_delete_permission = True
        else:
            # 查询全部时，检查发布人员是否是当前用户
            has_edit_permission = (publisher == current_user_display_name)
            has_delete_permission = (publisher == current_user_display_name)
        
        if has_edit_permission or has_delete_permission:
            menu.addSeparator()
        
        # 修改操作（仅当前用户的数据）
        if has_edit_permission:
            edit_action = QAction(QIcon(":/icons/common/edit.png"), "修改固件信息", self)
            edit_action.triggered.connect(lambda: self.edit_firmware(row))
            menu.addAction(edit_action)
        
        # 删除操作
        if has_delete_permission:
            delete_action = QAction(QIcon(":/icons/common/delete.png"), "删除固件", self)
            delete_action.triggered.connect(lambda: self.delete_firmware(row))
            menu.addAction(delete_action)
        
        # 显示菜单
        menu.exec_(self.result_table.viewport().mapToGlobal(pos))
    
    def copy_download_url_from_data(self, row):
        """从数据中复制下载链接"""
        from PyQt5.QtWidgets import QApplication
        
        if row >= len(self.filtered_list):
            return
        
        firmware = self.filtered_list[row]
        download_url = firmware.get('download_url', '')
        if download_url:
            clipboard = QApplication.clipboard()
            clipboard.setText(download_url)
            self.show_success(f"已复制下载链接: {download_url[:50]}{'...' if len(download_url) > 50 else ''}", 2000)
    
    def edit_firmware(self, row):
        """修改固件信息"""
        if row >= len(self.filtered_list):
            return
        
        firmware = self.filtered_list[row]
        firmware_id = firmware.get('id', '')
        identifier = firmware.get('identifier', '')
        publisher = firmware.get('publisher', '')
        
        if not firmware_id:
            self.show_error("无法获取固件ID")
            return
        
        # 检查权限：只能修改当前用户的固件
        current_user_display_name = self.get_current_user_display_name()
        
        if self.is_current_user_query:
            # 查询当前用户时，所有结果都可以编辑
            pass
        else:
            # 查询全部时，检查发布人员是否是当前用户
            if publisher != current_user_display_name:
                self.show_error(f"无权限修改：只能修改自己发布的固件（发布人员: {publisher}）")
                return
        
        # 显示加载提示
        self.show_progress(f"正在加载固件详情: {identifier}...")
        
        # 在后台线程中获取详情
        from PyQt5.QtCore import QThread, pyqtSignal
        
        class GetDetailThread(QThread):
            finished_signal = pyqtSignal(dict)
            error_signal = pyqtSignal(str)
            
            def __init__(self, firmware_id):
                super().__init__()
                self.firmware_id = firmware_id
            
            def run(self):
                detail = get_firmware_detail(self.firmware_id)
                if detail:
                    self.finished_signal.emit(detail)
                else:
                    self.error_signal.emit("获取固件详情失败，可能该固件不存在或无权限访问")
        
        detail_thread = GetDetailThread(firmware_id)
        detail_thread.finished_signal.connect(lambda detail: self.show_edit_dialog(firmware_id, detail))
        detail_thread.error_signal.connect(lambda msg: self.show_error(msg))
        detail_thread.finished.connect(lambda: detail_thread.deleteLater())
        self.thread_mgr.add("detail", detail_thread)
        detail_thread.start()
        
        # 保存线程引用
        self._detail_thread = detail_thread
    
    def show_edit_dialog(self, firmware_id, firmware_data):
        """显示修改对话框"""
        self.show_info("加载完成")
        
        # 创建并显示修改对话框
        dialog = EditFirmwareDialog(firmware_id, firmware_data, self)
        
        result = dialog.exec_()
        if result == EditFirmwareDialog.Accepted:
            # 用户点击了提交
            result_data = dialog.get_result()
            if result_data:
                # 传递固件ID和更新的数据
                self.submit_firmware_update(firmware_id, result_data)
        else:
            # 用户取消了修改
            self.show_info("已取消修改固件")
    
    def submit_firmware_update(self, firmware_id, data):
        """提交固件更新"""
        identifier = data.get('device_identify', '未知')
        self.show_progress(f"正在提交修改: {identifier}...")
        
        # 在后台线程中提交更新
        from PyQt5.QtCore import QThread, pyqtSignal
        
        class UpdateThread(QThread):
            finished_signal = pyqtSignal(bool, str)
            
            def __init__(self, firmware_id, data):
                super().__init__()
                self.firmware_id = firmware_id
                self.data = data
            
            def run(self):
                success, message = update_firmware(self.firmware_id, self.data)
                self.finished_signal.emit(success, message)
        
        update_thread = UpdateThread(firmware_id, data)
        # 传递固件ID和更新的数据到回调函数
        update_thread.finished_signal.connect(
            lambda success, msg: self.on_update_finished(success, msg, firmware_id, data)
        )
        update_thread.finished.connect(lambda: update_thread.deleteLater())
        self.thread_mgr.add("update", update_thread)
        update_thread.start()
        
        # 保存线程引用
        self._update_thread = update_thread
    
    def on_update_finished(self, success, message, firmware_id, updated_data):
        """更新完成回调"""
        if success:
            identifier = updated_data.get('device_identify', '未知')
            self.show_success(f"修改成功: {identifier}")
            
            # 只更新表格中已显示的字段，不重新查询
            self.update_table_row(firmware_id, updated_data)
        else:
            self.show_error(f"修改失败: {message}")
    
    def update_table_row(self, firmware_id, updated_data):
        """更新表格中的指定行"""
        # 在 filtered_list 中找到对应的固件
        for idx, firmware in enumerate(self.filtered_list):
            if firmware.get('id') == firmware_id:
                # 更新表格中显示的字段
                # 列0: 固件标识
                identifier = updated_data.get('device_identify', '')
                if identifier:
                    item = QTableWidgetItem(identifier)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    # 保留下载链接
                    download_url = firmware.get('download_url', '')
                    item.setData(Qt.UserRole, download_url)
                    self.result_table.setItem(idx, 0, item)
                    firmware['identifier'] = identifier
                
                # 列2: 开始时间
                start_time = updated_data.get('start_time', '')
                if start_time:
                    item = QTableWidgetItem(start_time)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.result_table.setItem(idx, 2, item)
                    firmware['start_time'] = start_time
                
                # 列3: 结束时间
                end_time = updated_data.get('end_time', '')
                if end_time:
                    item = QTableWidgetItem(end_time)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.result_table.setItem(idx, 3, item)
                    firmware['end_time'] = end_time
                
                # 列5: 发布备注
                remark = updated_data.get('create_comment', '')
                if remark is not None:  # 允许空字符串
                    item = QTableWidgetItem(remark)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.result_table.setItem(idx, 5, item)
                    firmware['remark'] = remark
                
                break
    
    def delete_firmware(self, row):
        """删除固件"""
        from PyQt5.QtWidgets import QMessageBox
        
        if row >= len(self.filtered_list):
            return
        
        firmware = self.filtered_list[row]
        firmware_id = firmware.get('id', '')
        identifier = firmware.get('identifier', '')
        publisher = firmware.get('publisher', '')
        
        if not firmware_id:
            self.show_error("无法获取固件ID")
            return
        
        # 检查权限：只能删除当前用户的固件
        current_user_display_name = self.get_current_user_display_name()
        
        if self.is_current_user_query:
            # 查询当前用户时，所有结果都可以删除
            pass
        else:
            # 查询全部时，检查发布人员是否是当前用户
            if publisher != current_user_display_name:
                self.show_error(f"无权限删除：只能删除自己发布的固件（发布人员: {publisher}）")
                return
        
        # 创建自定义确认对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('确认删除')
        msg_box.setText(f'确定要删除固件 "{identifier}" 吗？')
        msg_box.setInformativeText('此操作不可恢复！')
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        
        # 自定义按钮图标和大小
        yes_btn = msg_box.button(QMessageBox.Yes)
        no_btn = msg_box.button(QMessageBox.No)
        
        if yes_btn:
            yes_btn.setText("")
            yes_btn.setIcon(QIcon(":/icons/common/ok.png"))
            yes_btn.setIconSize(QSize(20, 20))
            yes_btn.setFixedSize(60, 32)
        
        if no_btn:
            no_btn.setText("")
            no_btn.setIcon(QIcon(":/icons/common/cancel.png"))
            no_btn.setIconSize(QSize(20, 20))
            no_btn.setFixedSize(60, 32)
        
        # 应用样式
        StyleManager.apply_to_widget(msg_box, "DIALOG")
        
        # 延迟设置深色标题栏
        QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
        
        reply = msg_box.exec_()
        
        if reply == QMessageBox.Yes:
            # 执行删除
            self.show_progress(f"正在删除固件: {identifier}...")
            
            # 在后台线程中执行删除
            from PyQt5.QtCore import QThread, pyqtSignal
            
            class DeleteThread(QThread):
                finished_signal = pyqtSignal(bool, str)
                
                def __init__(self, firmware_id):
                    super().__init__()
                    self.firmware_id = firmware_id
                
                def run(self):
                    success, message = delete_firmware(self.firmware_id)
                    self.finished_signal.emit(success, message)
            
            delete_thread = DeleteThread(firmware_id)
            delete_thread.finished_signal.connect(lambda success, msg: self.on_delete_finished(success, msg, identifier))
            delete_thread.finished.connect(lambda: delete_thread.deleteLater())
            self.thread_mgr.add("delete", delete_thread)
            delete_thread.start()
            
            # 保存线程引用，防止被垃圾回收
            self._delete_thread = delete_thread
    
    def on_delete_finished(self, success, message, identifier):
        """删除完成回调"""
        if success:
            self.show_success(f"删除成功: {identifier}")
            # 刷新当前页数据
            self.query_with_page(self.current_page)
        else:
            self.show_error(f"删除失败: {message}")
    
    def copy_download_url(self, row, col):
        """复制下载链接（旧方法，保留兼容性）"""
        from PyQt5.QtWidgets import QApplication
        
        item = self.result_table.item(row, col)
        if item:
            download_url = item.data(Qt.UserRole)
            if download_url:
                clipboard = QApplication.clipboard()
                clipboard.setText(download_url)
                self.show_success(f"已复制下载链接: {download_url[:50]}{'...' if len(download_url) > 50 else ''}", 2000)
    
    def cleanup(self):
        """清理资源"""
        # 停止所有线程
        self.thread_mgr.stop_all()
