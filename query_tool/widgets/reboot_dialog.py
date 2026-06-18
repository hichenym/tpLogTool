"""
设备重启对话框
"""
from PyQt5.QtWidgets import (
    QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon
from .adaptive_dialog import AdaptiveDialog
from .custom_widgets import set_dark_title_bar
from query_tool.ui import (
    BodyLabel,
    ElevatedCardWidget,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    RadioButton,
)
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.utils import StyleManager
from query_tool.utils.logger import logger
from query_tool.utils.session_manager import SessionManager
from query_tool.utils.thread_manager import ThreadManager
import json


class StatusQueryThread(QThread):
    """状态查询线程"""
    finished_signal = pyqtSignal(bool, str)  # is_online, message
    
    def __init__(self, sn, device_query, dev_id=None):
        super().__init__()
        self.sn = sn
        self.device_query = device_query
        self.dev_id = dev_id
    
    def run(self):
        """执行查询"""
        try:
            from query_tool.utils import check_device_online
            is_online = check_device_online(self.sn, self.device_query, dev_id=self.dev_id)
            if is_online:
                self.finished_signal.emit(True, "在线")
            else:
                self.finished_signal.emit(False, "离线")
        except Exception as e:
            self.finished_signal.emit(False, f"查询失败: {str(e)}")


class WakeDeviceThread(QThread):
    """唤醒设备线程"""
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, dev_id, sn, device_query):
        super().__init__()
        self.dev_id = dev_id
        self.sn = sn
        self.device_query = device_query
    
    def run(self):
        """执行唤醒"""
        try:
            from query_tool.utils import wake_device_smart
            
            # 使用智能唤醒：唤醒后自动检查在线状态
            is_online = wake_device_smart(
                self.dev_id, 
                self.sn, 
                self.device_query,
                max_times=3
            )
            
            if is_online:
                self.finished_signal.emit(True, "唤醒成功")
            else:
                self.finished_signal.emit(False, "唤醒失败")
        except Exception as e:
            self.finished_signal.emit(False, f"唤醒出错: {str(e)}")


class RebootThread(QThread):
    """重启设备线程"""
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, sn, reboot_time, token, host):
        super().__init__()
        self.sn = sn
        self.reboot_time = reboot_time
        self.token = token
        self.host = host
    
    def run(self):
        """执行重启"""
        try:
            session = SessionManager().get_session()
            
            url = f"https://{self.host}/api/seetong-siot-device/console/device/operate/sendCommand"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic c2VldG9uZ19jbG91ZF9hZG1pbjpzZWV0b25nX2Nsb3VkX2FkbWluX3NlY3JldA==",
                "Seetong-Auth": self.token,
            }
            
            # 构建参数
            params_dict = {"reboot_time": self.reboot_time}
            params_json = json.dumps(params_dict)
            
            data = {
                "moduleCode": "default",
                "code": "reboot",
                "params": params_json,
                "sn": self.sn,
                "sourceType": "1"
            }
            
            response = session.post(url, json=data, headers=headers, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 200 and result.get('success'):
                    self.finished_signal.emit(True, "重启命令已发送")
                else:
                    msg = result.get('msg', '操作失败')
                    self.finished_signal.emit(False, msg)
            else:
                self.finished_signal.emit(False, f"HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"重启出错: {e}")
            self.finished_signal.emit(False, f"重启出错: {str(e)}")


class RebootDialog(AdaptiveDialog):
    """设备重启对话框"""
    
    def __init__(self, sn, dev_id, device_query, parent=None):
        super().__init__(parent)
        self.sn = sn
        self.dev_id = dev_id
        self.device_query = device_query
        self.is_online = False
        
        # 线程管理器
        self.thread_mgr = ThreadManager()
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)
        
        self.init_ui()
        
        # 对话框打开时立即查询状态
        self.query_status()
    
    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass

    def _create_card_section(self, title):
        card = ElevatedCardWidget(self)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title_label = BodyLabel(title)
        title_label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")
        layout.addWidget(title_label)
        if not QFLUENT_WIDGETS_AVAILABLE:
            card.setStyleSheet(
                f"""
                QFrame {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )
        return card, layout

    @staticmethod
    def _caption_label(text, width=None):
        label = BodyLabel(text)
        if width is not None:
            label.setFixedWidth(width)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px; border: none;")
        return label

    @staticmethod
    def _info_label(text):
        label = BodyLabel(text)
        label.setStyleSheet(f"color: {t('status_info')}; font-size: 13px; border: none;")
        return label

    def _apply_icon_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _set_status_state(self, text, color_role):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {t(color_role)}; font-size: 12px; border: none;")
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("设备重启")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (450, 250),
            min_size=(360, 220),
            layout_margins=(20, 20, 20, 20),
            spacing=15,
            max_width_ratio=0.75,
            max_height_ratio=0.70,
        )
        
        # 设备信息（设备名称和SN在一行，蓝色字体）
        # 获取设备名称
        device_name = "未知设备"
        if self.device_query and not self.device_query.init_error:
            try:
                device_name = self.device_query.get_device_name(self.dev_id)
                if not device_name:
                    device_name = "未命名设备"
            except Exception as e:
                logger.debug(f"获取设备名称失败: {e}")
                pass
        
        info_label = self._info_label(f"设备: {device_name}    SN: {self.sn}")
        
        layout.addWidget(info_label)
        
        # 操作分组
        operation_group, operation_layout = self._create_card_section("操作")
        
        # 在线状态区
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)
        
        status_label_text = self._caption_label("在线状态:", width=70)
        
        self.status_label = BodyLabel("● 查询中...")
        self.status_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px; border: none;")
        self.status_label.setFixedWidth(80)  # 固定宽度，防止文本变化时位置移动
        
        # 唤醒按钮（只显示图标）
        self.wake_btn = PushButton("")
        self.wake_btn.setIcon(QIcon(":/icons/device/werk_up_all.png"))
        self.wake_btn.setIconSize(QSize(16, 16))
        self.wake_btn.setFixedSize(32, 32)
        self.wake_btn.setEnabled(False)
        self.wake_btn.setToolTip("唤醒设备")
        self.wake_btn.clicked.connect(self.on_wake)
        
        # 刷新按钮
        self.refresh_btn = PushButton("")
        self.refresh_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_btn.setIconSize(QSize(16, 16))
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setToolTip("刷新状态")
        self.refresh_btn.clicked.connect(self.on_refresh)
        
        self._apply_icon_button_style(self.wake_btn)
        self._apply_icon_button_style(self.refresh_btn)
        
        status_layout.addWidget(status_label_text)
        status_layout.addWidget(self.status_label)
        status_layout.addSpacing(5)  # 固定间距
        status_layout.addWidget(self.wake_btn)
        status_layout.addSpacing(5)  # 固定间距
        status_layout.addWidget(self.refresh_btn)
        status_layout.addStretch()
        
        operation_layout.addWidget(status_widget)
        
        # 重启时间选择（与在线状态对齐）
        time_widget = QWidget()
        time_layout = QHBoxLayout(time_widget)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(10)
        
        time_label = self._caption_label("重启时间:", width=70)
        
        self.radio_now = RadioButton("立即重启")
        self.radio_now.setChecked(True)
        self.radio_now.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        
        self.radio_delay = RadioButton("5分钟后重启")
        self.radio_delay.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.radio_now)
        self.button_group.addButton(self.radio_delay)
        
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.radio_now)
        time_layout.addWidget(self.radio_delay)
        time_layout.addStretch()
        
        operation_layout.addWidget(time_widget)
        
        layout.addWidget(operation_group)
        
        layout.addSpacing(15)
        
        # 操作按钮（右对齐）
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.confirm_btn = PrimaryPushButton("确定")
        self.confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        self.confirm_btn.setIconSize(QSize(20, 20))
        self.confirm_btn.setFixedSize(88, 32)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self.on_confirm)
        
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(20, 20))
        self.cancel_btn.setFixedSize(88, 32)
        self._apply_secondary_button_style(self.cancel_btn)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def query_status(self):
        """查询设备在线状态"""
        self._set_status_state("● 查询中...", "text_hint")
        
        # 禁用按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 启动查询线程
        if self.device_query and not self.device_query.init_error:
            thread = StatusQueryThread(self.sn, self.device_query, self.dev_id)
            thread.finished_signal.connect(self.on_status_query_finished)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("status_query", thread)
            thread.start()
        else:
            self._set_status_state("● 查询失败", "text_hint")
    
    def on_status_query_finished(self, is_online, message):
        """状态查询完成"""
        self.is_online = is_online
        
        if is_online:
            self._set_status_state("● 在线", "status_online")
        else:
            self._set_status_state("● 离线", "status_offline")
        
        # 启用按钮
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
    
    def on_refresh(self):
        """刷新状态"""
        self.query_status()
    
    def on_wake(self):
        """唤醒设备"""
        # 显示唤醒中状态
        self._set_status_state("● 唤醒中...", "status_pending")
        
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        
        # 启动唤醒线程
        thread = WakeDeviceThread(self.dev_id, self.sn, self.device_query)
        thread.finished_signal.connect(self.on_wake_finished)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("wake_device", thread)
        thread.start()
    
    def on_wake_finished(self, success, message):
        """唤醒完成"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        
        # 唤醒完成后直接更新状态，不显示查询中
        if success:
            # 唤醒成功，设备在线
            self.is_online = True
            self._set_status_state("● 在线", "status_online")
        else:
            # 唤醒失败，恢复之前的状态显示
            if self.is_online:
                self._set_status_state("● 在线", "status_online")
            else:
                self._set_status_state("● 离线", "status_offline")
    
    def on_confirm(self):
        """确认重启"""
        # 禁用所有按钮
        self.wake_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        
        # 不显示查询中提示，直接后台查询
        # 重新查询状态
        if self.device_query and not self.device_query.init_error:
            thread = StatusQueryThread(self.sn, self.device_query, self.dev_id)
            thread.finished_signal.connect(self.on_confirm_status_checked)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("confirm_status_query", thread)
            thread.start()
        else:
            if self.parent():
                self.parent().show_error("查询状态失败，操作取消")
            self.restore_buttons()
    
    def on_confirm_status_checked(self, is_online, message):
        """确认前状态检查完成"""
        if not is_online:
            self._set_status_state("● 离线", "status_offline")
            if self.parent():
                self.parent().show_warning("当前状态显示离线，继续尝试下发，最终结果以服务端返回为准")
        self.send_reboot_command()
    
    def send_reboot_command(self):
        """发送重启命令"""
        # 获取重启时间
        if self.radio_now.isChecked():
            reboot_time = "now"
        else:
            reboot_time = "after_five_minute"
        
        # 启动重启线程
        if self.device_query and self.device_query.token:
            thread = RebootThread(self.sn, reboot_time, self.device_query.token, self.device_query.host)
            thread.finished_signal.connect(self.on_reboot_finished)
            thread.finished.connect(lambda: thread.deleteLater())
            self.thread_mgr.add("reboot", thread)
            thread.start()
        else:
            if self.parent():
                self.parent().show_error("无法获取访问令牌，操作失败")
            self.restore_buttons()
    
    def on_reboot_finished(self, success, message):
        """重启命令发送完成"""
        if success:
            if self.parent():
                self.parent().show_success(f"重启命令已发送: {self.sn}")
            self.accept()
        else:
            if self.parent():
                self.parent().show_error(f"重启失败: {message}")
            self.restore_buttons()
    
    def restore_buttons(self):
        """恢复按钮状态"""
        self.wake_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

    def refresh_theme(self):
        if hasattr(self, "wake_btn"):
            self._apply_icon_button_style(self.wake_btn)
        if hasattr(self, "refresh_btn"):
            self._apply_icon_button_style(self.refresh_btn)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
        if hasattr(self, "radio_now"):
            self.radio_now.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, "radio_delay"):
            self.radio_delay.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, "status_label"):
            if self.status_label.text().endswith("在线"):
                self._set_status_state(self.status_label.text(), "status_online")
            elif self.status_label.text().endswith("离线"):
                self._set_status_state(self.status_label.text(), "status_offline")
            elif "唤醒中" in self.status_label.text():
                self._set_status_state(self.status_label.text(), "status_pending")
            else:
                self._set_status_state(self.status_label.text(), "text_hint")


