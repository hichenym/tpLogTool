"""
批量采集类型选择对话框
用户选择要采集的数据类型后，打开对应的批量采集对话框
"""

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from query_tool.ui import (
    BodyLabel,
    ElevatedCardWidget,
    PrimaryPushButton,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
)
from query_tool.utils import StyleManager
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.widgets.custom_widgets import set_dark_title_bar


class CollectTypeSelectorDialog(AdaptiveDialog):
    """批量采集类型选择对话框"""

    def __init__(self, devices, thread_count, device_query=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.thread_count = thread_count
        self.device_query = device_query
        self.parent_window = parent
        self.type_buttons = []
        self.empty_state_label = None

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        self.init_ui()

    def showEvent(self, event):
        """对话框显示时设置深色标题栏"""
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

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
        return card, layout, title_label

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("批量采集类型")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (460, 180),
            min_size=(380, 150),
            layout_margins=(20, 20, 20, 20),
            spacing=15,
            max_width_ratio=0.76,
            max_height_ratio=0.60,
        )

        card, card_layout, self.title_label = self._create_card_section("选择采集类型")

        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        from query_tool.utils.data_collect_api import get_enabled_collect_types

        collect_types = get_enabled_collect_types()

        if not collect_types:
            self.empty_state_label = BodyLabel("暂无可用的采集类型")
            self.empty_state_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 13px; border: none;")
            self.empty_state_label.setAlignment(Qt.AlignCenter)
            button_layout.addWidget(self.empty_state_label)
        else:
            for index, (type_id, type_info) in enumerate(collect_types.items()):
                button_cls = PrimaryPushButton if index == 0 else PushButton
                btn = button_cls(type_info["name"])
                if type_info.get("icon"):
                    btn.setIcon(QIcon(type_info["icon"]))
                btn.setIconSize(QSize(16, 16))
                btn.setMinimumWidth(110)
                btn.setFixedHeight(34)
                if button_cls is PushButton:
                    self._apply_secondary_button_style(btn)
                btn.clicked.connect(
                    lambda checked=False, tid=type_id, tinfo=type_info: self.on_type_selected(tid, tinfo)
                )
                self.type_buttons.append(btn)
                button_layout.addWidget(btn)

        button_layout.addStretch()
        card_layout.addWidget(button_widget)
        layout.addWidget(card)
        layout.addStretch()

        button_layout_bottom = QHBoxLayout()
        button_layout_bottom.setContentsMargins(0, 0, 0, 0)
        button_layout_bottom.addStretch()

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.cancel_btn.setIconSize(QSize(18, 18))
        self.cancel_btn.setFixedSize(92, 34)
        self._apply_secondary_button_style(self.cancel_btn)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout_bottom.addWidget(self.cancel_btn)

        layout.addLayout(button_layout_bottom)

    @staticmethod
    def _exec_dialog(dialog):
        exec_method = getattr(dialog, "exec", None)
        if callable(exec_method):
            return exec_method()
        return dialog.exec_()

    def on_type_selected(self, type_id, type_info):
        """选择采集类型后打开对应的批量对话框"""
        self.accept()

        if type_id == "battery":
            from query_tool.widgets.batch_battery_collect_dialog import BatchBatteryCollectDialog

            dialog = BatchBatteryCollectDialog(
                self.devices, self.thread_count, self.device_query, self.parent_window
            )
            if self.parent_window and hasattr(self.parent_window, "status_message"):
                dialog.log_message.connect(lambda msg: self.parent_window.show_progress(msg))
            self._exec_dialog(dialog)

    def refresh_theme(self):
        if hasattr(self, "title_label"):
            self.title_label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")
        if self.empty_state_label is not None:
            self.empty_state_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 13px; border: none;")
        for button in self.type_buttons[1:]:
            self._apply_secondary_button_style(button)
        if hasattr(self, "cancel_btn"):
            self._apply_secondary_button_style(self.cancel_btn)
