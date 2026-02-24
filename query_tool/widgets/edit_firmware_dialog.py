"""
修改固件对话框
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QDateTimeEdit, QGroupBox, QFormLayout, QWidget,
    QLineEdit, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QDateTime, QEvent, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon
from .custom_widgets import set_dark_title_bar
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
        
        self.setFixedSize(700, 550)  # 增加尺寸以容纳新字段
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 固件标识信息（在表单上方，无边框）- 仅编辑模式显示
        if not self.is_create_mode:
            identifier = self.firmware_data.get('device_identify', '未知')
            info_label = QLabel(f"固件标识: {identifier}")
            info_label.setStyleSheet("""
                QLabel {
                    color: #4a9eff;
                    font-size: 13px;
                }
            """)
            layout.addWidget(info_label)
        
        # 表单区域
        form_group = QGroupBox("编辑")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(15, 20, 15, 15)
        
        # 通用样式
        readonly_style = """
            QLineEdit {
                background-color: #2b2b2b;
                color: #909090;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
        """
        
        editable_style = """
            QTextEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
            QTextEdit:focus {
                border: 1px solid #6a6a6a;
            }
        """
        
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
        self.file_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #6a6a6a;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #606060;
                border: 1px solid #3c3c3c;
            }
        """)
        self.file_btn.clicked.connect(self.on_select_file)
        
        self.file_status_label = QLabel("未选择文件")
        self.file_status_label.setStyleSheet("color: #909090; font-size: 12px;")
        self.file_status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        file_layout.addWidget(self.file_btn)
        file_layout.addWidget(self.file_status_label, 1)  # 添加伸展因子，让标签占据剩余空间
        
        form_layout.addRow(file_label, file_widget)
        
        # 2. 固件标识（只读）
        identifier_label = QLabel("<span style='color: red;'>*</span> 固件标识:")
        self.identifier_input = QLineEdit()
        self.identifier_input.setReadOnly(True)
        self.identifier_input.setFocusPolicy(Qt.NoFocus)  # 禁止获取焦点
        self.identifier_input.setFixedHeight(28)
        self.identifier_input.setStyleSheet(readonly_style)
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
        
        # 5. 支持升级的设备SN
        sn_label = QLabel("<span style='color: red;'>*</span> 升级设备SN:")
        sn_label.setToolTip("每行一个SN，支持多个设备")
        self.sn_text = QTextEdit()
        self.sn_text.setPlaceholderText("每行输入一个设备SN...")
        self.sn_text.setMinimumHeight(100)
        self.sn_text.setMaximumHeight(100)
        self.sn_text.setStyleSheet(editable_style)
        # 连接文本变化信号，实时验证SN长度和是否为空
        self.sn_text.textChanged.connect(self.on_sn_text_changed)
        self.sn_text.textChanged.connect(self.validate_form)
        form_layout.addRow(sn_label, self.sn_text)
        
        # 6. 可升级时间段（两个时间控件水平排列）
        time_label = QLabel("升级时间段:")
        time_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        time_widget = QWidget()
        time_widget.setFixedHeight(28)
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        # 时间控件样式
        datetime_style = """
            QDateTimeEdit {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
            QDateTimeEdit:hover {
                border: 1px solid #6a6a6a;
            }
            QDateTimeEdit:disabled {
                background-color: #2b2b2b;
                color: #606060;
                border: 1px solid #3c3c3c;
            }
            QDateTimeEdit::drop-down {
                border: none;
                background-color: #505050;
                width: 24px;
                border-left: 1px solid #555555;
            }
            QDateTimeEdit::down-arrow {
                image: none;
                width: 0px;
            }
            QCalendarWidget {
                background-color: #3c3c3c;
                color: #e0e0e0;
            }
            QCalendarWidget QToolButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 4px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #4a4a4a;
            }
            QCalendarWidget QMenu {
                background-color: #3c3c3c;
                color: #e0e0e0;
            }
            QCalendarWidget QSpinBox {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #3c3c3c;
                color: #e0e0e0;
                selection-background-color: #0d7377;
                selection-color: #ffffff;
            }
        """
        
        # 开始时间
        self.start_time_edit = ClickableDateTimeEdit()
        self.start_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time_edit.setCalendarPopup(True)
        self.start_time_edit.setMinimumWidth(180)
        self.start_time_edit.setStyleSheet(datetime_style)
        self.start_time_edit.setButtonSymbols(QDateTimeEdit.UpDownArrows)
        
        # 分隔符
        separator_label = QLabel("—")
        separator_label.setStyleSheet("color: #909090; font-size: 14px;")
        
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
        
        form_layout.addRow(time_label, time_widget)
        
        layout.addWidget(form_group)
        
        # 按钮区域
        layout.addSpacing(15)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # 按钮样式
        button_style = """
            QPushButton {
                background-color: #404040;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #6a6a6a;
            }
            QPushButton:pressed {
                background-color: #3c3c3c;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #606060;
                border: 1px solid #3c3c3c;
            }
        """
        
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
        self.comment_text.setPlainText(comment)
        
        # 加载支持升级的设备SN
        support_sn = self.firmware_data.get('support_sn', '')
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
                # 红色边框（1px，参考端口穿透样式）
                self.sn_text.setStyleSheet("""
                    QTextEdit {
                        background-color: #404040;
                        color: #e0e0e0;
                        border: 1px solid #FF0000;
                        border-radius: 3px;
                        padding: 4px;
                    }
                    QTextEdit:focus {
                        border: 1px solid #FF0000;
                    }
                """)
            else:
                # 正常边框
                self.sn_text.setStyleSheet("""
                    QTextEdit {
                        background-color: #404040;
                        color: #e0e0e0;
                        border: 1px solid #555555;
                        border-radius: 3px;
                        padding: 4px;
                    }
                    QTextEdit:focus {
                        border: 1px solid #6a6a6a;
                    }
                """)
        else:
            # 如果为空，恢复正常边框
            self.sn_text.setStyleSheet("""
                QTextEdit {
                    background-color: #404040;
                    color: #e0e0e0;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 4px;
                }
                QTextEdit:focus {
                    border: 1px solid #6a6a6a;
                }
            """)
    
    def on_comment_text_changed(self):
        """发布备注文本变化时，如果有内容则取消红框"""
        text = self.comment_text.toPlainText().strip()
        if text:
            # 有内容时恢复正常边框
            self.comment_text.setStyleSheet("""
                QTextEdit {
                    background-color: #404040;
                    color: #e0e0e0;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 4px;
                }
                QTextEdit:focus {
                    border: 1px solid #6a6a6a;
                }
            """)
    
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
            
            # 校验文件名是否以 firmware_ 开头
            if not file_name.startswith('firmware_'):
                self.file_status_label.setText("文件非法")
                self.file_status_label.setStyleSheet("color: #FF0000;")  # 红色
                if self.parent():
                    self.parent().show_error("文件非法：固件文件名必须以 firmware_ 开头")
                return
            
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
        self.file_status_label.setStyleSheet("color: #FFA500;")  # 橙色
        
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
            self.file_status_label.setStyleSheet("color: #00FF00;")  # 绿色
            
            # 更新固件标识
            firmware_identity = data.get('firmware_identity', '')
            if firmware_identity:
                self.identifier_input.setText(firmware_identity)
                self.firmware_data['device_identify'] = firmware_identity
            
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
            self.file_status_label.setStyleSheet("color: #FF0000;")  # 红色
            
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
