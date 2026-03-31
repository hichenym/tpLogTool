"""
修改固件对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDateTimeEdit, QGroupBox, QFormLayout, QWidget,
    QLineEdit, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QAbstractItemView
)
from PyQt5.QtCore import Qt, QDateTime, QEvent, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon
from .custom_widgets import set_dark_title_bar
from query_tool.utils.theme_manager import t
from query_tool.utils import StyleManager
from query_tool.utils.logger import logger
from query_tool.utils.thread_manager import ThreadManager
import os


class ClickableDateTimeEdit(QDateTimeEdit):
    """可点击弹出日历的时间编辑控件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
    
    def mousePressEvent(self, event):
        """鼠标点击时弹出日历"""
        if event.button() == Qt.LeftButton:
            # 显示日历弹出窗口
            self.calendarWidget().show()
        super().mousePressEvent(event)


class FileUploadThread(QThread):
    """文件上传后台线程"""
    finished_signal = pyqtSignal(bool, dict, str)  # success, data, message
    
    def __init__(self, file_path, firmware_id, session, csrf_token):
        super().__init__()
        self.file_path = file_path
        self.firmware_id = firmware_id
        self.session = session
        self.csrf_token = csrf_token
    
    def run(self):
        """执行上传"""
        try:
            # 准备上传数据
            with open(self.file_path, 'rb') as f:
                files = {'file': (os.path.basename(self.file_path), f, 'application/octet-stream')}
                data = {
                    'type': '3',
                    'id': str(self.firmware_id)
                }
                
                # 设置请求头（包含 CSRF token）
                headers = {
                    'X-CSRF-TOKEN': self.csrf_token,
                    'Accept': '*/*',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': f'https://update.seetong.com/admin/update/debug-firmware/{self.firmware_id}/edit'
                }
                
                # 上传到临时目录
                upload_url = 'https://update.seetong.com/admin/update/file/temp/upload'
                response = self.session.post(upload_url, files=files, data=data, headers=headers, timeout=300)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        self.finished_signal.emit(True, result, "上传成功")
                    else:
                        msg = result.get('msg', '上传失败')
                        self.finished_signal.emit(False, {}, msg)
                else:
                    self.finished_signal.emit(False, {}, f"上传失败: HTTP {response.status_code}")
        except Exception as e:
            self.finished_signal.emit(False, {}, f"上传出错: {str(e)}")


class DeviceSnQueryThread(QThread):
    """轻量级设备SN查询线程 - 只查询设备名称、SN和型号"""
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    success = pyqtSignal(list)  # [{device_name, sn, model}, ...]

    def __init__(self, phone, env, username, password):
        super().__init__()
        self.phone = phone
        self.env = env
        self.username = username
        self.password = password

    def run(self):
        try:
            from query_tool.utils.device_query import DeviceQuery
            self.progress.emit("正在登录...")
            query = DeviceQuery(self.env, self.username, self.password)
            if query.init_error:
                self.error.emit(query.init_error)
                return

            self.progress.emit("正在查询用户信息...")
            user_response = query.get_user_by_mobile(self.phone)
            if not user_response or not user_response.get('data'):
                self.error.emit("未找到该手机号对应的用户")
                return
            records = user_response['data'].get('records', [])
            if not records:
                self.error.emit("未找到该手机号对应的用户")
                return
            user_id = records[0].get('id')
            if not user_id:
                self.error.emit("无法获取用户ID")
                return

            self.progress.emit("正在查询绑定设备...")
            devices_response = query.get_user_bind_devices(user_id)
            if not devices_response or not devices_response.get('data'):
                self.error.emit("未找到该用户的绑定设备")
                return
            devices = devices_response['data']
            if not devices:
                self.error.emit("该用户暂无绑定设备")
                return

            self.progress.emit(f"正在查询 {len(devices)} 台设备的型号...")
            results = []
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def get_device_model(device):
                device_sn = device.get('deviceSn', '')
                device_name = device.get('deviceName', '')
                model = ''
                if device_sn:
                    try:
                        info = query.get_device_info(dev_sn=device_sn)
                        recs = info.get('data', {}).get('records', [])
                        standard_sn = recs[0].get('devSN', device_sn) if recs else device_sn
                        header = query.get_device_header(standard_sn)
                        if header and header.get('data'):
                            model = header['data'].get('productName', '')
                        device_sn = standard_sn
                    except Exception:
                        pass
                return {'device_name': device_name, 'sn': device_sn, 'model': model}

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(get_device_model, d) for d in devices]
                for i, future in enumerate(as_completed(futures)):
                    results.append(future.result())
                    if (i + 1) % 5 == 0 or (i + 1) == len(devices):
                        self.progress.emit(f"正在查询设备型号... {i + 1}/{len(devices)}")

            self.success.emit(results)
        except Exception as e:
            self.error.emit(f"查询失败：{str(e)}")


class SnQueryDialog(QDialog):
    """设备SN查询结果对话框 - 打开时自动查询，按型号过滤"""

    def __init__(self, phone='', model_filter='', parent=None):
        super().__init__(parent)
        self.phone = phone
        self.model_filter = model_filter
        self.all_devices = []
        self.selected_sns = []
        self._checkboxes = []
        self.thread_mgr = ThreadManager()
        self.setWindowTitle("查询设备SN")
        self.setFixedSize(500, 420)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._init_ui()
        # 打开后自动开始查询
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self._on_query)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 状态标签
        self.status_label = QLabel("正在查询...")
        self.status_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        self.status_label.setFixedHeight(18)
        layout.addWidget(self.status_label)

        # 结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "设备名称", "SN"])
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.setFrameShape(QTableWidget.NoFrame)
        self.table.verticalHeader().setVisible(False)

        header = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 30)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignCenter)

        self.table.setStyleSheet(StyleManager.get_TABLE())
        layout.addWidget(self.table, 1)

        # 全选行（放在表格下方）
        select_all_row = QHBoxLayout()
        select_all_row.setContentsMargins(0, 0, 0, 0)
        self.select_all_cb_bottom = QCheckBox("全选")
        self.select_all_cb_bottom.setStyleSheet(f"color: {t('text_primary')}; font-size: 11px;")
        self.select_all_cb_bottom.stateChanged.connect(self._on_select_all)
        select_all_row.addWidget(self.select_all_cb_bottom)
        select_all_row.addStretch()
        layout.addLayout(select_all_row)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_style = StyleManager.get_ACTION_BUTTON()

        self.add_btn = QPushButton("添加到SN")
        self.add_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.add_btn.setIconSize(QSize(18, 18))
        self.add_btn.setFixedHeight(28)
        self.add_btn.setStyleSheet(btn_style)
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add)

        cancel_btn = QPushButton("取消")
        cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        cancel_btn.setIconSize(QSize(18, 18))
        cancel_btn.setFixedHeight(28)
        cancel_btn.setStyleSheet(btn_style)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_query(self):
        from query_tool.utils.config import get_account_config
        env, username, password = get_account_config()
        if not username or not password:
            self.status_label.setText("运维账号未配置，请先在设置中配置")
            self.status_label.setStyleSheet(f"color: {t('status_offline')}; font-size: 11px;")
            return

        self.status_label.setText("正在查询...")
        self.status_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        self.table.setRowCount(0)

        thread = DeviceSnQueryThread(self.phone, env, username, password)
        thread.progress.connect(lambda msg: self.status_label.setText(msg))
        thread.error.connect(self._on_query_error)
        thread.success.connect(self._on_query_success)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("sn_query", thread)
        thread.start()
        self._query_thread = thread

    def _on_query_error(self, msg):
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {t('status_offline')}; font-size: 11px;")

    def _on_query_success(self, devices):
        self.all_devices = devices

        # 按型号过滤
        if self.model_filter:
            filtered = [d for d in devices if d.get('model', '') == self.model_filter]
        else:
            filtered = devices

        if not filtered:
            total = len(devices)
            self.status_label.setText(
                f"共 {total} 台设备，无匹配型号 [{self.model_filter}] 的设备" if self.model_filter
                else "该账号暂无绑定设备"
            )
            self.status_label.setStyleSheet(f"color: {t('status_pending')}; font-size: 11px;")
            self.table.setRowCount(0)
            return

        self.status_label.setText(f"共 {len(devices)} 台设备，匹配 {len(filtered)} 台")
        self.status_label.setStyleSheet(f"color: {t('status_online')}; font-size: 11px;")
        self._fill_table(filtered)

    def _fill_table(self, devices):
        self.table.setRowCount(len(devices))
        self._checkboxes = []
        self.select_all_cb_bottom.blockSignals(True)
        self.select_all_cb_bottom.setChecked(False)
        self.select_all_cb_bottom.blockSignals(False)
        for row, dev in enumerate(devices):
            cb = QCheckBox()
            cb.stateChanged.connect(self._update_add_btn)
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cb_widget)
            self._checkboxes.append(cb)

            name_item = QTableWidgetItem(dev.get('device_name', ''))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 1, name_item)

            sn_item = QTableWidgetItem(dev.get('sn', ''))
            sn_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 2, sn_item)

        self.table.resizeRowsToContents()

    def _on_select_all(self, state):
        checked = (state == Qt.Checked)
        for cb in self._checkboxes:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._update_add_btn()

    def _update_add_btn(self):
        has_checked = any(cb.isChecked() for cb in self._checkboxes)
        self.add_btn.setEnabled(has_checked)

    def _on_add(self):
        self.selected_sns = []
        for row, cb in enumerate(self._checkboxes):
            if cb.isChecked():
                sn_item = self.table.item(row, 2)
                if sn_item and sn_item.text():
                    self.selected_sns.append(sn_item.text())
        self.accept()

    def get_selected_sns(self):
        return self.selected_sns


class EditFirmwareDialog(QDialog):
    """修改固件信息对话框"""
    
    def __init__(self, firmware_id, firmware_data, parent=None):
        super().__init__(parent)
        self.firmware_id = firmware_id  # None 表示新增模式
        self.firmware_data = firmware_data
        self.result_data = None
        self.session = None  # 将从父窗口获取session
        self.selected_file_name = None  # 保存选择的文件名
        self.is_create_mode = (firmware_id is None)  # 是否为新增模式
        
        # 线程管理器
        self.thread_mgr = ThreadManager()
        
        # 获取session（从firmware_api模块）
        try:
            from query_tool.utils.firmware_api import login
            self.session = login()
        except Exception as e:
            logger.error(f"获取固件session失败: {e}")
        
        self.init_ui()
        self.load_data()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
    
    def init_ui(self):
        """初始化UI"""
        # 根据模式设置标题
        if self.is_create_mode:
            self.setWindowTitle("新增固件")
        else:
            self.setWindowTitle("固件信息修改")
        
        self.setFixedSize(700, 560)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 固件标识信息（在表单上方，无边框）- 仅编辑模式显示
        if not self.is_create_mode:
            identifier = self.firmware_data.get('device_identify', '未知')
            info_label = QLabel(f"固件标识: {identifier}")
            info_label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px;")
            layout.addWidget(info_label)
        
        # 表单区域
        form_group = QGroupBox("编辑")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 20, 15, 15)
        
        # 通用样式
        readonly_style = StyleManager.get_READONLY_INPUT()
        
        editable_style = StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit")
        
        # 1. 固件文件上传
        file_label = QLabel("固件文件:")
        file_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 垂直居中对齐
        file_widget = QWidget()
        file_widget.setFixedHeight(28)  # 与按钮高度一致
        file_layout = QHBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(10)
        
        self.file_btn = QPushButton("选择文件")
        self.file_btn.setFixedHeight(28)
        self.file_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.file_btn.clicked.connect(self.on_select_file)
        
        self.file_status_label = QLabel("未选择文件")
        self.file_status_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px;")
        self.file_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        file_layout.addWidget(self.file_btn)
        file_layout.addWidget(self.file_status_label, 1)  # 添加伸展因子，让标签占据剩余空间
        
        form_layout.addRow(file_label, file_widget)
        
        # 2. 固件标识（可编辑）
        identifier_label = QLabel("<span style='color: red;'>*</span> 固件标识:")
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("自动获取或手动输入固件标识...")
        self.identifier_input.setFixedHeight(28)
        self.identifier_input.setStyleSheet(StyleManager.get_style("PLAINTEXT_EDIT_TABLE").replace("QPlainTextEdit", "QLineEdit"))
        # 连接文本变化信号，实时验证
        self.identifier_input.textChanged.connect(self.validate_form)
        form_layout.addRow(identifier_label, self.identifier_input)
        
        # 3. 文件MD5（只读）
        md5_label = QLabel("<span style='color: red;'>*</span> 文件MD5:")
        self.md5_input = QLineEdit()
        self.md5_input.setReadOnly(True)
        self.md5_input.setFocusPolicy(Qt.NoFocus)  # 禁止获取焦点
        self.md5_input.setFixedHeight(28)
        self.md5_input.setStyleSheet(readonly_style)
        form_layout.addRow(md5_label, self.md5_input)
        
        # 4. 发布备注
        comment_label = QLabel("<span style='color: red;'>*</span> 发布备注:")
        self.comment_text = QTextEdit()
        self.comment_text.setPlaceholderText("输入发布备注...")
        self.comment_text.setMinimumHeight(60)
        self.comment_text.setMaximumHeight(60)
        self.comment_text.setStyleSheet(editable_style)
        # 连接文本变化信号，实时验证
        self.comment_text.textChanged.connect(self.on_comment_text_changed)
        self.comment_text.textChanged.connect(self.validate_form)
        form_layout.addRow(comment_label, self.comment_text)
        
        # 5. 支持升级的设备SN（标签、输入框、右侧账号+查询按钮）
        sn_label = QLabel("<span style='color: red;'>*</span> 升级设备SN:")
        sn_label.setToolTip("每行一个SN，支持多个设备")
        sn_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        sn_right_widget = QWidget()
        sn_right_widget.setFixedHeight(100)  # 与SN输入框等高，避免多余空间
        sn_right_layout = QHBoxLayout(sn_right_widget)
        sn_right_layout.setContentsMargins(0, 0, 0, 0)
        sn_right_layout.setSpacing(8)

        self.sn_text = QTextEdit()
        self.sn_text.setPlaceholderText("每行输入一个设备SN...")
        self.sn_text.setFixedHeight(100)
        self.sn_text.setStyleSheet(editable_style)
        self.sn_text.textChanged.connect(self.on_sn_text_changed)
        self.sn_text.textChanged.connect(self.validate_form)

        # 右侧：账号输入框 + 查询按钮（垂直排列）
        sn_btn_widget = QWidget()
        sn_btn_layout = QVBoxLayout(sn_btn_widget)
        sn_btn_layout.setContentsMargins(0, 0, 0, 0)
        sn_btn_layout.setSpacing(4)

        from PyQt5.QtWidgets import QComboBox
        self.sn_phone_input = QComboBox()
        self.sn_phone_input.setEditable(True)
        self.sn_phone_input.setInsertPolicy(QComboBox.NoInsert)
        self.sn_phone_input.lineEdit().setPlaceholderText("手机号...")
        self.sn_phone_input.setFixedSize(100, 28)
        self.sn_phone_input.setStyleSheet(StyleManager.get_COMBOBOX())
        # 加载账号历史（与设备查询页面同步）
        self._load_phone_history()

        self.sn_query_btn = QPushButton("查询设备")
        self.sn_query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.sn_query_btn.setIconSize(QSize(14, 14))
        self.sn_query_btn.setFixedSize(100, 28)
        self.sn_query_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.sn_query_btn.clicked.connect(self.on_query_device_sn)

        sn_btn_layout.addWidget(self.sn_phone_input)
        sn_btn_layout.addWidget(self.sn_query_btn)

        self.sn_temp_fill_btn = QPushButton("临时填充")
        self.sn_temp_fill_btn.setFixedSize(100, 28)
        self.sn_temp_fill_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        self.sn_temp_fill_btn.clicked.connect(self._on_temp_fill_sn)
        sn_btn_layout.addWidget(self.sn_temp_fill_btn)

        sn_btn_widget.setFixedHeight(100)  # 与SN输入框等高

        sn_right_layout.addWidget(self.sn_text, 1)
        sn_right_layout.addWidget(sn_btn_widget)

        form_layout.addRow(sn_label, sn_right_widget)
        
        # 6. 可升级时间段（两个时间控件水平排列）
        time_label = QLabel("升级时间段:")
        time_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        time_widget = QWidget()
        time_widget.setFixedHeight(28)
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        datetime_style = ""  # 全局 QSS 已覆盖 QDateTimeEdit
        
        # 开始时间
        self.start_time_edit = ClickableDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setMinimumWidth(180)
        self.start_time_edit.setStyleSheet(datetime_style)
        self.start_time_edit.setButtonSymbols(QDateTimeEdit.UpDownArrows)
        
        # 分隔符
        separator_label = QLabel("—")
        separator_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 14px;")
        
        # 结束时间
        self.end_time_edit = ClickableDateTimeEdit()
        self.end_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_time_edit.setCalendarPopup(True)
        self.end_time_edit.setMinimumWidth(180)
        self.end_time_edit.setStyleSheet(datetime_style)
        self.end_time_edit.setButtonSymbols(QDateTimeEdit.UpDownArrows)
        
        time_layout.addWidget(self.start_time_edit)
        time_layout.addWidget(separator_label)
        time_layout.addWidget(self.end_time_edit)
        time_layout.addStretch()
        
        # 今天快捷按钮，与右侧按钮列对齐（同宽 100px）
        today_btn = QPushButton("今天")
        today_btn.setFixedSize(100, 28)
        today_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        today_btn.clicked.connect(self._on_set_today)
        time_layout.addWidget(today_btn)
        
        # 调整 time_widget 高度以容纳按钮
        time_widget.setFixedHeight(28)
        
        form_layout.addRow(time_label, time_widget)
        
        layout.addWidget(form_group)
        
        # 按钮区域
        layout.addSpacing(15)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        button_style = StyleManager.get_ACTION_BUTTON()
        
        self.submit_btn = QPushButton()
        self.submit_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.submit_btn.setIconSize(QSize(18, 18))
        self.submit_btn.setFixedSize(60, 28)
        self.submit_btn.setStyleSheet(button_style)
        self.submit_btn.clicked.connect(self.on_submit)
        
        self.cancel_btn = QPushButton()
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(18, 18))
        self.cancel_btn.setFixedSize(60, 28)
        self.cancel_btn.setStyleSheet(button_style)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.submit_btn)
        button_layout.addSpacing(10)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def load_data(self):
        """加载当前数据"""
        # 加载固件标识
        identifier = self.firmware_data.get('device_identify', '')
        self.identifier_input.setText(identifier)
        
        # 加载文件MD5
        md5 = self.firmware_data.get('file_md5', '')
        self.md5_input.setText(md5)
        
        # 加载发布备注
        comment = self.firmware_data.get('create_comment', '')
        # 新增模式下，默认填写 "test"
        if self.is_create_mode and not comment:
            comment = 'test'
        self.comment_text.setPlainText(comment)
        
        # 加载支持升级的设备SN
        support_sn = self.firmware_data.get('support_sn', '')
        # 新增模式下，默认填写 "AABBCCDDEEFFGGHH"
        if self.is_create_mode and not support_sn:
            support_sn = 'AABBCCDDEEFFGGHH'
        self.sn_text.setPlainText(support_sn)
        
        # 加载开始时间
        start_time_str = self.firmware_data.get('start_time', '')
        if start_time_str:
            try:
                start_time = QDateTime.fromString(start_time_str, "yyyy-MM-dd HH:mm:ss")
                if start_time.isValid():
                    self.start_time_edit.setDateTime(start_time)
                else:
                    self.start_time_edit.setDateTime(QDateTime.currentDateTime())
            except Exception as e:
                logger.warning(f"解析开始时间失败: {e}")
                self.start_time_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.start_time_edit.setDateTime(QDateTime.currentDateTime())
        
        # 加载结束时间
        end_time_str = self.firmware_data.get('end_time', '')
        if end_time_str:
            try:
                end_time = QDateTime.fromString(end_time_str, "yyyy-MM-dd HH:mm:ss")
                if end_time.isValid():
                    self.end_time_edit.setDateTime(end_time)
                else:
                    self.end_time_edit.setDateTime(QDateTime.currentDateTime())
            except Exception as e:
                logger.warning(f"解析结束时间失败: {e}")
                self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        
        # 初始验证表单状态
        self.validate_form()
    
    def validate_form(self):
        """验证表单，控制确认按钮状态"""
        # 必填字段验证
        identifier = self.identifier_input.text().strip()
        md5 = self.md5_input.text().strip()
        comment = self.comment_text.toPlainText().strip()
        sn_text = self.sn_text.toPlainText().strip()
        
        # 获取非空SN行
        sn_lines = [line.strip() for line in sn_text.split('\n') if line.strip()]
        
        # 检查SN是否有效（每行长度必须为16）
        sn_valid = True
        if sn_lines:
            for line in sn_lines:
                if len(line) != 16:
                    sn_valid = False
                    break
        else:
            sn_valid = False  # 没有SN也是无效的
        
        # 所有必填字段都有值且SN有效时，启用确认按钮
        if identifier and md5 and comment and sn_valid:
            self.submit_btn.setEnabled(True)
        else:
            self.submit_btn.setEnabled(False)
    
    def on_sn_text_changed(self):
        """SN文本变化时，验证每行SN长度是否为16，以及是否为空"""
        text = self.sn_text.toPlainText()
        lines = text.split('\n')
        
        # 获取非空行
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # 如果有内容，检查长度是否正确
        if non_empty_lines:
            # 检查是否有长度不为16的SN
            has_invalid = False
            for line in non_empty_lines:
                if len(line) != 16:
                    has_invalid = True
                    break
            
            # 根据验证结果设置边框颜色
            if has_invalid:
                self.sn_text.setStyleSheet(
                    f"QTextEdit {{ background-color: {t('bg_light')}; color: {t('text_primary')}; "
                    f"border: 1px solid {t('status_offline')}; border-radius: 3px; padding: 4px; }}"
                    f"QTextEdit:focus {{ border: 1px solid {t('status_offline')}; }}"
                )
            else:
                self.sn_text.setStyleSheet(StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit"))
        else:
            self.sn_text.setStyleSheet(StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit"))
    
    def on_comment_text_changed(self):
        """发布备注文本变化时，如果有内容则取消红框"""
        text = self.comment_text.toPlainText().strip()
        if text:
            self.comment_text.setStyleSheet(StyleManager.get_PLAINTEXT_EDIT_TABLE().replace("QPlainTextEdit", "QTextEdit"))
    
    def on_query_device_sn(self):
        """查询设备SN - 直接弹出结果对话框"""
        phone = self.sn_phone_input.currentText().strip()
        if not phone:
            if self.parent():
                self.parent().show_warning("请输入手机号")
            return

        # 从固件标识提取型号（取第一个 '-' 前的部分）
        identifier = self.identifier_input.text().strip()
        model_filter = identifier.split('-')[0] if identifier and '-' in identifier else ''

        dialog = SnQueryDialog(phone=phone, model_filter=model_filter, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            sns = dialog.get_selected_sns()
            if sns:
                # 保存手机号到历史
                self._save_phone_to_history(phone)
                # 获取已有的SN，去重后追加
                existing_text = self.sn_text.toPlainText().strip()
                existing_sns = set(line.strip() for line in existing_text.split('\n') if line.strip())
                new_sns = [sn for sn in sns if sn not in existing_sns]
                if new_sns:
                    if existing_text:
                        self.sn_text.setPlainText(existing_text + '\n' + '\n'.join(new_sns))
                    else:
                        self.sn_text.setPlainText('\n'.join(new_sns))

    def _load_phone_history(self):
        """从配置加载账号历史（与设备查询页面同步）"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        if app_config.phone_history:
            self.sn_phone_input.addItems(app_config.phone_history)

    def _save_phone_to_history(self, phone):
        """保存手机号到历史（与设备查询页面同步）"""
        from query_tool.utils import config_manager
        app_config = config_manager.load_app_config()
        if phone in app_config.phone_history:
            app_config.phone_history.remove(phone)
        app_config.phone_history.insert(0, phone)
        app_config.phone_history = app_config.phone_history[:5]
        config_manager.save_app_config(app_config)
        # 刷新下拉列表
        self.sn_phone_input.clear()
        self.sn_phone_input.addItems(app_config.phone_history)

    def _on_temp_fill_sn(self):
        """临时填充SN"""
        self.sn_text.setPlainText('AABBCCDDEEFFGGHH')

    def _on_set_today(self):
        """将时间段设置为今天"""
        from PyQt5.QtCore import QDateTime, QDate, QTime
        today = QDate.currentDate()
        self.start_time_edit.setDateTime(QDateTime(today, QTime(0, 0, 0)))
        self.end_time_edit.setDateTime(QDateTime(today, QTime(23, 59, 59)))

    def on_select_file(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择固件文件",
            "",
            "所有文件 (*.*)"
        )
        
        if file_path:
            # 获取文件名
            file_name = os.path.basename(file_path)
            
            # 显示文件名
            self.file_status_label.setText(f"已选择: {file_name}")
            
            # 保存文件名，上传成功后显示
            self.selected_file_name = file_name
            
            # 开始上传
            self.start_upload(file_path)
    
    def start_upload(self, file_path):
        """开始上传文件"""
        if not self.session:
            if self.parent():
                self.parent().show_error("无法获取登录会话，请重试")
            return
        
        # 获取 CSRF token
        csrf_token = self.firmware_data.get('_token', '')
        if not csrf_token:
            if self.parent():
                self.parent().show_error("无法获取 CSRF token，请重试")
            return
        
        # 禁用控件
        self.file_btn.setEnabled(False)
        self.submit_btn.setEnabled(False)
        self.file_status_label.setText("上传中...")
        self.file_status_label.setStyleSheet(f"color: {t('status_pending')};  # 橙色")  # 橙色
        
        # 在主窗口显示上传提示
        if self.parent():
            self.parent().show_progress("正在上传固件文件...")
        
        # 创建上传线程（新增模式传 0 作为 firmware_id）
        upload_id = self.firmware_id if self.firmware_id else 0
        thread = FileUploadThread(file_path, upload_id, self.session, csrf_token)
        thread.finished_signal.connect(self.on_upload_finished)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("file_upload", thread)
        thread.start()
    
    def on_upload_finished(self, success, data, message):
        """上传完成回调"""
        # 恢复控件
        self.file_btn.setEnabled(True)
        self.submit_btn.setEnabled(True)
        
        if success:
            # 更新显示 - 显示完整文件名
            if self.selected_file_name:
                self.file_status_label.setText(f"上传成功: {self.selected_file_name}")
            else:
                self.file_status_label.setText(f"上传成功")
            self.file_status_label.setStyleSheet(f"color: {t('status_online')};  # 绿色")  # 绿色
            
            # 更新固件标识（如果自动获取成功）
            firmware_identity = data.get('firmware_identity', '')
            if firmware_identity:
                self.identifier_input.setText(firmware_identity)
                self.firmware_data['device_identify'] = firmware_identity
            else:
                # 自动获取失败，使用文件名（不含后缀）作为固件标识
                if self.selected_file_name:
                    # 去掉文件扩展名
                    file_name_without_ext = os.path.splitext(self.selected_file_name)[0]
                    self.identifier_input.setText(file_name_without_ext)
                    self.firmware_data['device_identify'] = file_name_without_ext
                    if self.parent():
                        self.parent().show_warning(f"固件标识自动获取失败，已使用文件名: {file_name_without_ext}")
                else:
                    # 没有文件名，清空输入框
                    self.identifier_input.clear()
                    if self.parent():
                        self.parent().show_warning("固件标识自动获取失败，请手动填写")
            
            # 更新文件MD5
            file_md5 = data.get('file_md5', '')
            if file_md5:
                self.md5_input.setText(file_md5)
                self.firmware_data['file_md5'] = file_md5
            
            # 更新文件相关字段
            if 'file_url' in data:
                self.firmware_data['file_url'] = data['file_url']
            if 'file_path' in data:
                self.firmware_data['file_path'] = data['file_path']
            if 'file_temp_path' in data:
                self.firmware_data['file_temp_path'] = data['file_temp_path']
            if 'file_formal_path' in data:
                self.firmware_data['file_formal_path'] = data['file_formal_path']
            
            # 在主窗口显示成功提示
            if self.parent():
                self.parent().show_success("文件上传成功！")
            
            # 触发表单验证，更新确认按钮状态
            self.validate_form()
        else:
            # 显示错误
            self.file_status_label.setText(f"上传失败")
            self.file_status_label.setStyleSheet(f"color: {t('status_offline')};  # 红色")  # 红色
            
            # 清空固件标识和MD5，等待用户重新上传或手动填写
            self.identifier_input.clear()
            self.md5_input.setText('')
            
            # 在主窗口显示错误提示
            if self.parent():
                self.parent().show_error(f"上传失败: {message}")
            
            # 触发表单验证，更新确认按钮状态
            self.validate_form()
        
        # 强制清除焦点，让对话框本身获取焦点
        self.setFocus()
        
        # 加载开始时间
        start_time_str = self.firmware_data.get('start_time', '')
        if start_time_str:
            try:
                start_time = QDateTime.fromString(start_time_str, "yyyy-MM-dd HH:mm:ss")
                if start_time.isValid():
                    self.start_time_edit.setDateTime(start_time)
                else:
                    self.start_time_edit.setDateTime(QDateTime.currentDateTime())
            except Exception as e:
                logger.warning(f"on_upload_finished解析开始时间失败: {e}")
                self.start_time_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.start_time_edit.setDateTime(QDateTime.currentDateTime())
        
        # 加载结束时间
        end_time_str = self.firmware_data.get('end_time', '')
        if end_time_str:
            try:
                end_time = QDateTime.fromString(end_time_str, "yyyy-MM-dd HH:mm:ss")
                if end_time.isValid():
                    self.end_time_edit.setDateTime(end_time)
                else:
                    self.end_time_edit.setDateTime(QDateTime.currentDateTime())
            except Exception as e:
                logger.warning(f"on_upload_finished解析结束时间失败: {e}")
                self.end_time_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self.end_time_edit.setDateTime(QDateTime.currentDateTime())
    
    def on_submit(self):
        """提交修改"""
        from PyQt5.QtWidgets import QMessageBox
        from PyQt5.QtCore import QTimer
        
        # 由于按钮已经通过validate_form控制启用/禁用
        # 这里只需要做最终的数据收集和提交
        
        # 收集表单数据
        identifier = self.identifier_input.text().strip()
        md5 = self.md5_input.text().strip()
        comment = self.comment_text.toPlainText().strip()
        sn_text = self.sn_text.toPlainText().strip()
        
        # 获取非空SN行
        sn_lines = [line.strip() for line in sn_text.split('\n') if line.strip()]
        
        # 再次验证（防御性编程）
        if not identifier or not md5 or not comment or not sn_lines:
            logger.warning("提交时发现必填字段为空，这不应该发生")
            return
        
        # 验证SN长度
        for line in sn_lines:
            if len(line) != 16:
                logger.warning(f"提交时发现无效SN: {line}")
                return
        
        support_sn = '\n'.join(sn_lines)
        
        start_time = self.start_time_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        end_time = self.end_time_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        
        # 验证时间
        if self.start_time_edit.dateTime() >= self.end_time_edit.dateTime():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("时间错误")
            msg_box.setText("开始时间必须早于结束时间！")
            msg_box.setStandardButtons(QMessageBox.Ok)
            QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
            msg_box.exec_()
            return
        
        # 构建提交数据（包含所有字段）
        self.result_data = self.firmware_data.copy()
        self.result_data['device_identify'] = identifier  # 使用输入框中的固件标识
        self.result_data['file_md5'] = md5  # 使用输入框中的MD5
        self.result_data['support_sn'] = support_sn
        self.result_data['start_time'] = start_time
        self.result_data['end_time'] = end_time
        self.result_data['create_comment'] = comment
        
        # 新增模式需要添加 _method 字段为空（不是 PUT）
        if self.is_create_mode:
            # 移除 _method 字段（新增不需要）
            if '_method' in self.result_data:
                del self.result_data['_method']
        
        self.accept()
    
    def get_result(self):
        """获取修改结果"""
        return self.result_data

