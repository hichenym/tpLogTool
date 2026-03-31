"""
批量采集类型选择对话框
用户选择要采集的数据类型后，打开对应的批量采集对话框
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from query_tool.widgets.custom_widgets import set_dark_title_bar
from query_tool.utils.theme_manager import t
from query_tool.utils import StyleManager


class CollectTypeSelectorDialog(QDialog):
    """批量采集类型选择对话框"""
    
    def __init__(self, devices, thread_count, device_query=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.thread_count = thread_count
        self.device_query = device_query  # 复用已有的DeviceQuery对象
        self.parent_window = parent
        self.init_ui()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量采集类型")
        self.setFixedSize(400, 120)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 采集类型按钮区域
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)
        
        # 动态生成采集类型按钮
        from query_tool.utils.data_collect_api import get_enabled_collect_types
        collect_types = get_enabled_collect_types()
        
        button_style = StyleManager.get_ACTION_BUTTON()
        
        if not collect_types:
            no_type_label = QLabel("暂无可用的采集类型")
            no_type_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 13px;")
            no_type_label.setAlignment(Qt.AlignCenter)
            button_layout.addWidget(no_type_label)
        else:
            for type_id, type_info in collect_types.items():
                btn = QPushButton(type_info['name'])
                if type_info.get('icon'):
                    btn.setIcon(QIcon(type_info['icon']))
                btn.setStyleSheet(button_style)
                btn.setMinimumWidth(100)
                btn.clicked.connect(
                    lambda checked, tid=type_id, tinfo=type_info: self.on_type_selected(tid, tinfo)
                )
                button_layout.addWidget(btn)
        
        button_layout.addStretch()
        layout.addWidget(button_widget)
        
        layout.addStretch()
        
        # 取消按钮
        button_layout_bottom = QHBoxLayout()
        button_layout_bottom.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        cancel_btn.clicked.connect(self.reject)
        button_layout_bottom.addWidget(cancel_btn)
        
        layout.addLayout(button_layout_bottom)
    
    def on_type_selected(self, type_id, type_info):
        """选择采集类型后打开对应的批量对话框"""
        self.accept()  # 关闭选择对话框
        
        # 动态导入并打开对应的批量对话框
        if type_id == 'battery':
            from query_tool.widgets.batch_battery_collect_dialog import BatchBatteryCollectDialog
            dialog = BatchBatteryCollectDialog(
                self.devices, self.thread_count, self.device_query, self.parent_window
            )
            # 将日志信号连接到父页面（如果父页面支持）
            if self.parent_window and hasattr(self.parent_window, 'status_message'):
                dialog.log_message.connect(
                    lambda msg: self.parent_window.show_progress(msg)
                )
            dialog.exec_()
        # 后续可添加其他类型
        # elif type_id == 'temperature':
        #     from query_tool.widgets.batch_temperature_collect_dialog import BatchTemperatureCollectDialog
        #     dialog = BatchTemperatureCollectDialog(self.devices, self.thread_count, self.parent_window)
        #     dialog.exec_()
