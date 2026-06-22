"""
错误码记录查询页面
展示设备错误码上报记录，支持多条件筛选和分页
"""
import sys
import os
from time import monotonic

from PyQt5.QtWidgets import (
    QFileDialog,
    QCompleter,
    QHeaderView,
    QMessageBox,
    QShortcut,
    QSizePolicy,
    QTableWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
)
from PyQt5.QtCore import Qt, QSize, QTimer, QStringListModel, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence
from PyQt5.QtGui import QFontMetrics

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import ButtonManager, ThreadManager, StyleManager
from query_tool.ui import (
    BodyLabel,
    EditableComboBox,
    ElevatedCardWidget,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    StrongBodyLabel,
    TableWidget,
)
from query_tool.utils.theme_manager import t, theme_manager
from query_tool.utils.error_record_api import MetaLoadThread, ErrorRecordQueryThread, _make_device_query
from query_tool.utils.logger import logger
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.widgets.custom_widgets import set_dark_title_bar, show_question_box


class _NoWheelComboBox(EditableComboBox):
    """禁用鼠标滚轮切换的可编辑下拉框"""
    def wheelEvent(self, event):
        event.ignore()


class DeviceInfoQueryThread(QThread):
    """根据 SN 查询设备详情线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, device_sn, fallback_model=""):
        super().__init__()
        self.device_sn = device_sn
        self.fallback_model = fallback_model

    def run(self):
        try:
            dq = _make_device_query()
            result = dq.get_device_info(dev_sn=self.device_sn)
            if not result.get("success"):
                raise RuntimeError(result.get("msg", "查询设备信息失败"))

            records = result.get("data", {}).get("records", [])
            if not records:
                raise RuntimeError("未查询到设备信息")

            record = records[0]
            dev_id = str(record.get("devId") or record.get("id") or "").strip()
            if not dev_id:
                raise RuntimeError("设备ID为空，无法获取详情")

            device_name = dq.get_device_name(dev_id)
            password = dq.get_cloud_password(dev_id) or ""
            version = dq.get_device_version(dev_id) or ""

            data = {
                "设备名称": device_name or record.get("deviceName", "") or record.get("devName", ""),
                "型号": record.get("devModel", "") or record.get("deviceModel", "") or record.get("model", "") or self.fallback_model,
                "SN": record.get("devSN", "") or record.get("deviceSn", "") or self.device_sn,
                "ID": dev_id,
                "密码": password,
                "版本号": version or record.get("fileVersion", "") or record.get("deviceIdentify", ""),
            }
            self.finished.emit(data)
        except Exception as e:
            logger.error(f"DeviceInfoQueryThread 异常: {e}")
            self.error.emit(str(e))


class DeviceInfoDialog(AdaptiveDialog):
    """设备信息弹窗"""

    def __init__(self, info, parent=None):
        super().__init__(parent)
        self.info = info
        self._key_col_width = 120

        self.setWindowTitle("设备信息")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        layout = self.init_dialog_layout(
            (560, 360),
            min_size=(360, 240),
            layout_margins=(20, 20, 20, 20),
            spacing=14,
            max_width_ratio=0.72,
            max_height_ratio=0.72,
        )

        self.info_card = ElevatedCardWidget(self)
        self.info_card.setObjectName("deviceInfoCard")
        card_layout = QVBoxLayout(self.info_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        self.tip_label = BodyLabel("双击内容可复制")
        card_layout.addWidget(self.tip_label)

        self.table = TableWidget(self.info_card)
        self.table.setRowCount(len(info))
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["字段", "内容"])
        self.table.setEditTriggers(TableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(TableWidget.SelectRows)
        self.table.setSelectionMode(TableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        for row, (key, value) in enumerate(info.items()):
            key_item = QTableWidgetItem(key)
            value_item = QTableWidgetItem(str(value or ""))
            self.table.setItem(row, 0, key_item)
            self.table.setItem(row, 1, value_item)

        self.table.cellDoubleClicked.connect(self._copy_cell_text)
        card_layout.addWidget(self.table)
        layout.addWidget(self.info_card)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = PushButton("关闭")
        self.close_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        self.close_btn.setIconSize(QSize(18, 18))
        self.close_btn.setMinimumWidth(96)
        self.close_btn.setFixedHeight(32)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self._adjust_table_size(info)
        self.refresh_theme()
        self.apply_adaptive_geometry()

    def showEvent(self, event):
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

    def _apply_card_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            self.info_card.setStyleSheet(
                f"""
                #deviceInfoCard {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )

    def refresh_theme(self):
        self.tip_label.setStyleSheet(f"color: {t('text_hint')}; border: none;")
        self._apply_secondary_button_style(self.close_btn)
        self._apply_card_style()
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.table, "TABLE")

    def _copy_cell_text(self, row, column):
        item = self.table.item(row, column)
        if not item:
            return
        from PyQt5.QtWidgets import QApplication
        text = item.text()
        if text:
            QApplication.clipboard().setText(text)
            parent = self.parent()
            if parent and hasattr(parent, 'show_success'):
                parent.show_success(f"已复制: {text}", 2000)

    def _adjust_table_size(self, info):
        metrics = QFontMetrics(self.table.font())

        key_width = max(
            [metrics.horizontalAdvance("字段")] +
            [metrics.horizontalAdvance(str(key)) for key in info.keys()]
        ) + 28

        value_width = max(
            [metrics.horizontalAdvance("内容")] +
            [max(metrics.horizontalAdvance(line) for line in str(value or "").splitlines() or [""]) for value in info.values()]
        ) + 40

        key_width = max(70, min(key_width, 180))
        value_width = max(220, min(value_width, 520))

        self._key_col_width = key_width
        self.table.setColumnWidth(0, key_width)

        default_row_h = self.table.verticalHeader().defaultSectionSize()
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, default_row_h)

        vertical_header_w = self.table.verticalHeader().width() if self.table.verticalHeader().isVisible() else 0
        frame_w = self.table.frameWidth() * 2
        total_w = key_width + value_width + vertical_header_w + frame_w + 2
        self.table.setMinimumWidth(total_w)

        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else self.contentsMargins()
        dialog_w = total_w + margins.left() + margins.right()

        header_h = self.table.horizontalHeader().height()
        rows_h = default_row_h * self.table.rowCount()
        frame_h = self.table.frameWidth() * 2
        table_h = header_h + rows_h + frame_h + 2
        self.table.setMinimumHeight(table_h)

        spacing = layout.spacing() if layout is not None else 0
        dialog_h = table_h + margins.top() + margins.bottom() + 32 + spacing * 2 + 24
        self._minimum_dialog_size = QSize(
            max(self._minimum_dialog_size.width(), dialog_w),
            max(self._minimum_dialog_size.height(), dialog_h),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.table.setColumnWidth(0, self._key_col_width)


class ExportProgressDialog(AdaptiveDialog):
    """导出过程中的进度弹窗。"""

    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在导出")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setModal(True)

        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)

        layout = self.init_dialog_layout(
            (420, 180),
            min_size=(320, 150),
            layout_margins=(18, 18, 18, 18),
            spacing=12,
            max_width_ratio=0.55,
            max_height_ratio=0.40,
        )

        self.card = ElevatedCardWidget(self)
        self.card.setObjectName("exportProgressCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)

        self.status_label = BodyLabel("正在拉取数据，请稍候...")
        self.status_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.status_label)

        self.progress_bar = ProgressBar()
        self.progress_bar.setRange(0, 0)
        card_layout.addWidget(self.progress_bar)

        self.cancel_btn = PushButton("取消")
        self.cancel_btn.setMinimumWidth(96)
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        self.cancel_btn.clicked.connect(self.reject)
        card_layout.addWidget(self.cancel_btn, 0, Qt.AlignRight)

        layout.addWidget(self.card)
        self.refresh_theme()

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass

    def refresh_theme(self):
        self.status_label.setStyleSheet(f"color: {t('text_primary')}; border: none;")
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.progress_bar, "PROGRESS_BAR")
            self.cancel_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
            self.card.setStyleSheet(
                f"""
                #exportProgressCard {{
                    border: 1px solid {t('border')};
                    border-radius: 6px;
                    background-color: transparent;
                }}
                """
            )


@register_page("记录", order=5, icon=":/icons/system/record.png")
class ErrorRecordPage(BasePage):
    """错误码记录查询页面"""

    META_AUTO_REFRESH_INTERVAL_SECONDS = 3600

    # 表格列定义：(表头, 数据字段, 初始宽度, 最小宽度)
    COLUMNS = [
        ("设备SN (双击查看设备信息)", "deviceSn", 220, 140),
        ("设备型号",      "deviceModel",     100,  70),
        ("设备版本",      "deviceIdentify",  200, 120),
        ("所属模块",      "module",          100,  70),
        ("错误码",        "errorCode",        80,  60),
        ("错误描述",      "errorMsg",        200,  80),
        ("触发时间",      "errorTime",       155, 155),
        ("上报时间",      "reportTime",      155, 155),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "记录"

        self.btn_manager = ButtonManager()
        self.thread_mgr = ThreadManager()

        # 元数据
        self._meta_loaded = False
        self._meta_loading = False
        self._meta_last_loaded_at = 0.0
        self._meta_request_label = "加载"
        self._model_map = {}        # {"TD53E30": ["TD53E30-3.0.x", ...]}
        self._module_list = []      # [{"key": "4G", "label": "4G模块"}]
        self._module_key_map = {}   # {"4G模块": "4G"}

        # 分页
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self.per_page = 100

        # 列宽防抖（窗口缩放和列拖拽分开）
        self._resize_timer = None
        self._col_resize_timer = None

        # 当前数据
        self._records = []

        self._init_ui()

    def _create_card_section(self, title, vertical_policy=QSizePolicy.Fixed):
        """创建统一的 Fluent 卡片区块。"""
        card = ElevatedCardWidget(self)
        card.setSizePolicy(QSizePolicy.Expanding, vertical_policy)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(StrongBodyLabel(title))
        return card, layout

    def _control_height(self, extra_padding: int = 12, minimum: int = 32) -> int:
        metrics = QFontMetrics(self.font())
        return max(minimum, metrics.height() + extra_padding)

    @staticmethod
    def _combo_line_edit(combo):
        getter = getattr(combo, "lineEdit", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            return None

    def _set_combo_placeholder(self, combo, text):
        setter = getattr(combo, "setPlaceholderText", None)
        if callable(setter):
            try:
                setter(text)
                return
            except Exception:
                pass

        line_edit = self._combo_line_edit(combo)
        if line_edit is not None:
            line_edit.setPlaceholderText(text)

    # ------------------------------------------------------------------ UI --

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.addWidget(self._create_filter_group())
        layout.addWidget(self._create_result_group())

        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(self.refresh_meta_btn)
        self.main_buttons.add(self.query_btn)
        self.main_buttons.add(self.reset_btn)

        self._bind_filter_change_events()

    def _bind_filter_change_events(self):
        """绑定筛选项变化事件，用于控制查询按钮状态"""
        self.sn_input.textChanged.connect(self._update_query_button_state)
        self.model_combo.currentTextChanged.connect(self._update_query_button_state)
        self.version_combo.currentTextChanged.connect(self._update_query_button_state)
        self.module_combo.currentTextChanged.connect(self._update_query_button_state)
        self.error_code_input.textChanged.connect(self._update_query_button_state)
        self.start_dt.textChanged.connect(self._update_query_button_state)
        self.end_dt.textChanged.connect(self._update_query_button_state)

        self._update_query_button_state()

    def _create_filter_group(self):
        group, gl = self._create_card_section("筛选条件")
        gl.setSpacing(8)
        control_height = self._control_height()

        # --- 第一行 ---
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self.sn_input = self._make_lineedit("输入设备SN...")
        self.model_combo = self._make_combo(editable=True, placeholder="选择或输入型号...")
        self.version_combo = self._make_combo(editable=True, placeholder="选择或输入版本...")

        row1.addWidget(self._label("设备SN:"))
        row1.addWidget(self.sn_input, 2)
        row1.addSpacing(10)
        row1.addWidget(self._label("设备型号:"))
        row1.addWidget(self.model_combo, 2)
        row1.addSpacing(10)
        row1.addWidget(self._label("设备版本:"))
        row1.addWidget(self.version_combo, 3)

        # --- 第二行 ---
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.module_combo = self._make_combo(editable=True, placeholder="选择或输入模块...")
        self.module_combo.setMaximumWidth(160)
        self.error_code_input = self._make_lineedit("输入错误码...")
        self.error_code_input.setMinimumWidth(120)

        self.start_dt = LineEdit()
        self.start_dt.setPlaceholderText("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setFixedHeight(control_height)

        self.end_dt = LineEdit()
        self.end_dt.setPlaceholderText("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setFixedHeight(control_height)

        self.query_btn = PrimaryPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setMinimumWidth(96)
        self.query_btn.setFixedHeight(control_height)
        self.query_btn.clicked.connect(self.on_query)

        self.refresh_meta_btn = PushButton("刷新数据")
        self.refresh_meta_btn.setIcon(QIcon(":/icons/device/reflash.png"))
        self.refresh_meta_btn.setIconSize(QSize(16, 16))
        self.refresh_meta_btn.setMinimumWidth(108)
        self.refresh_meta_btn.setFixedHeight(control_height)
        self.refresh_meta_btn.clicked.connect(self.on_refresh_meta)

        self.reset_btn = PushButton("重置")
        self.reset_btn.setIcon(QIcon(":/icons/common/clean.png"))
        self.reset_btn.setIconSize(QSize(16, 16))
        self.reset_btn.setMinimumWidth(96)
        self.reset_btn.setFixedHeight(control_height)
        self.reset_btn.clicked.connect(self.on_reset)

        range_sep = BodyLabel("-")
        range_sep.setFixedWidth(10)
        range_sep.setAlignment(Qt.AlignCenter)
        range_sep.setStyleSheet("border: none;")

        today_btn = PushButton("今")
        today_btn.setMinimumWidth(48)
        today_btn.setFixedHeight(control_height)
        today_btn.clicked.connect(self._fill_today)

        row2.addWidget(self._label("所属模块:"))
        row2.addWidget(self.module_combo, 2)
        row2.addSpacing(10)
        row2.addWidget(self._label("错误码:"))
        row2.addWidget(self.error_code_input, 1)
        row2.addSpacing(10)
        row2.addWidget(self._label("时间范围:"))
        row2.addWidget(self.start_dt, 2)
        row2.addWidget(range_sep)
        row2.addWidget(self.end_dt, 2)
        row2.addWidget(today_btn)
        row2.addSpacing(10)
        row2.addWidget(self.refresh_meta_btn)
        row2.addSpacing(4)
        row2.addWidget(self.query_btn)
        row2.addSpacing(4)
        row2.addWidget(self.reset_btn)

        gl.addLayout(row1)
        gl.addLayout(row2)

        # 型号变化时联动版本
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        return group

    def _create_result_group(self):
        group, gl = self._create_card_section("查询结果", QSizePolicy.Expanding)
        gl.setSpacing(12)
        label_height = max(24, self._control_height(extra_padding=8, minimum=24))

        col_count = len(self.COLUMNS)
        self.result_table = TableWidget()
        self.result_table.setColumnCount(col_count)
        self.result_table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self.result_table.setFocusPolicy(Qt.StrongFocus)
        self.result_table.setSelectionMode(TableWidget.SingleSelection)
        self.result_table.setSelectionBehavior(TableWidget.SelectRows)
        self.result_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.result_table.setShowGrid(True)
        self.result_table.setFrameShape(TableWidget.NoFrame)
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.result_table, "TABLE")

        header = self.result_table.horizontalHeader()
        header.setMinimumSectionSize(45)
        for i, (_, _, w, min_w) in enumerate(self.COLUMNS):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            self.result_table.setColumnWidth(i, w)
        header.sectionResized.connect(self._on_column_resized)

        # Ctrl+C 复制
        copy_sc = QShortcut(QKeySequence.Copy, self.result_table)
        copy_sc.activated.connect(self._copy_selected)
        self.result_table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # 分页栏
        pager = QHBoxLayout()
        pager.setContentsMargins(0, 2, 0, 0)
        pager.setSpacing(6)

        self.prev_btn = PushButton()
        self.prev_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_btn.setIconSize(QSize(16, 16))
        self.prev_btn.setFixedSize(36, 32)
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.on_prev_page)
        self._apply_icon_button_style(self.prev_btn)

        self.page_label = BodyLabel("[0/0]")
        self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        self.page_label.setMinimumHeight(label_height)
        self.page_label.setMinimumWidth(70)
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_btn = PushButton()
        self.next_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_btn.setIconSize(QSize(16, 16))
        self.next_btn.setFixedSize(36, 32)
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.on_next_page)
        self._apply_icon_button_style(self.next_btn)

        self.total_label = BodyLabel("")
        self.total_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        self.total_label.setMinimumHeight(label_height)
        self.total_label.setAlignment(Qt.AlignVCenter)

        self.export_csv_btn = PushButton("导出CSV")
        self.export_csv_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_csv_btn.setIconSize(QSize(16, 16))
        self.export_csv_btn.setMinimumWidth(108)
        self.export_csv_btn.setFixedHeight(self._control_height())
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self.on_export_csv)

        self.export_json_btn = PushButton("导出JSON")
        self.export_json_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_json_btn.setIconSize(QSize(16, 16))
        self.export_json_btn.setMinimumWidth(108)
        self.export_json_btn.setFixedHeight(self._control_height())
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.clicked.connect(self.on_export_json)

        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_btn)
        pager.addSpacing(8)
        pager.addWidget(self.total_label)
        pager.addStretch()
        pager.addWidget(self.export_csv_btn)
        pager.addSpacing(4)
        pager.addWidget(self.export_json_btn)

        gl.addWidget(self.result_table)
        gl.addLayout(pager)
        return group

    # --------------------------------------------------------- helpers ------

    @staticmethod
    def _label(text):
        lbl = BodyLabel(text)
        lbl.setFixedWidth(70)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setStyleSheet("border: none;")
        return lbl

    @staticmethod
    def _get_icon_button_stylesheet():
        return """
        QPushButton {
            min-width: 0px;
            padding: 0px;
            text-align: center;
        }
        """

    def _apply_icon_button_style(self, button):
        button.setStyleSheet(self._get_icon_button_stylesheet())

    def _make_lineedit(self, placeholder):
        w = LineEdit()
        w.setPlaceholderText(placeholder)
        w.setFixedHeight(self._control_height())
        return w

    def _make_combo(self, editable=False, placeholder=""):
        cb = _NoWheelComboBox()
        cb.setFixedHeight(self._control_height())
        cb.setFocusPolicy(Qt.StrongFocus)
        if editable:
            if hasattr(cb, "setEditable"):
                try:
                    cb.setEditable(True)
                except Exception:
                    pass
            if hasattr(cb, "setInsertPolicy"):
                no_insert = getattr(type(cb), "NoInsert", getattr(cb, "NoInsert", None))
                if no_insert is not None:
                    try:
                        cb.setInsertPolicy(no_insert)
                    except Exception:
                        pass
            self._set_combo_placeholder(cb, placeholder)
            if not QFLUENT_WIDGETS_AVAILABLE and hasattr(cb, "setCompleter"):
                completer = QCompleter()
                completer.setFilterMode(Qt.MatchContains)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
                cb.setCompleter(completer)
        return cb

    def _set_combo_items(self, combo, items, with_empty=True):
        """设置下拉框选项并刷新 completer"""
        combo.blockSignals(True)
        combo.clear()
        if with_empty:
            combo.addItem("")
        for item in items:
            combo.addItem(item)
        # 刷新 completer model
        completer_getter = getattr(combo, "completer", None)
        completer = completer_getter() if callable(completer_getter) else None
        if completer is not None:
            all_items = [combo.itemText(i) for i in range(combo.count())]
            completer.setModel(QStringListModel(all_items))
        combo.blockSignals(False)

    def _has_any_filter(self):
        """是否至少填写了一个筛选条件"""
        return any([
            self.sn_input.text().strip(),
            self.model_combo.currentText().strip(),
            self.version_combo.currentText().strip(),
            self.module_combo.currentText().strip(),
            self.error_code_input.text().strip(),
            self.start_dt.text().strip(),
            self.end_dt.text().strip(),
        ])

    def _update_query_button_state(self):
        """根据筛选条件和元数据加载状态更新查询按钮可用性"""
        can_query = self._meta_loaded and not self._meta_loading and self._has_any_filter()
        self.query_btn.setEnabled(can_query)

    # ---------------------------------------------------- page lifecycle ----

    def on_page_show(self):
        self.show_info("记录页面")
        self.adjust_table_columns()
        if not self._meta_loaded:
            self._load_meta()
        elif self._is_meta_stale():
            self._load_meta(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.adjust_table_columns)
        self._resize_timer.start(150)

    # ---------------------------------------------------- meta loading ------

    def _is_meta_stale(self):
        if not self._meta_loaded:
            return True
        if self._meta_last_loaded_at <= 0:
            return True
        return (monotonic() - self._meta_last_loaded_at) >= self.META_AUTO_REFRESH_INTERVAL_SECONDS

    def _capture_filter_state(self):
        return {
            "model": self.model_combo.currentText(),
            "version": self.version_combo.currentText(),
            "module": self.module_combo.currentText(),
        }

    def _restore_filter_state(self, state):
        if not state:
            self._on_model_changed(self.model_combo.currentText().strip())
            return

        self.model_combo.setCurrentText(state.get("model", ""))
        self._on_model_changed(self.model_combo.currentText().strip())
        self.version_combo.setCurrentText(state.get("version", ""))
        self.module_combo.setCurrentText(state.get("module", ""))

    def _set_meta_loading_state(self, loading):
        self._meta_loading = loading
        if loading:
            self.query_btn.setEnabled(False)
            self.refresh_meta_btn.setEnabled(False)
            self.refresh_meta_btn.setText("刷新中...")
            return

        self.refresh_meta_btn.setEnabled(True)
        self.refresh_meta_btn.setText("刷新数据")
        self._update_query_button_state()

    def _load_meta(self, force=False):
        if self._meta_loading or self.thread_mgr.is_running("meta"):
            return

        self._meta_request_label = "刷新" if force or self._meta_loaded else "加载"
        self.show_progress(f"正在{self._meta_request_label}型号和模块数据...")
        self._set_meta_loading_state(True)

        thread = MetaLoadThread()
        thread.finished.connect(self._on_meta_loaded)
        thread.error.connect(self._on_meta_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("meta", thread)
        thread.start()

    def _on_meta_loaded(self, model_map, module_list):
        # 读取刷新完成时界面上的最新筛选值，避免覆盖用户在刷新期间的输入。
        preserved_state = self._capture_filter_state()
        self._model_map = model_map
        self._module_list = module_list
        self._module_key_map = {m["label"]: m["key"] for m in module_list}
        self._meta_loaded = True
        self._meta_last_loaded_at = monotonic()

        # 填充型号下拉框
        self._set_combo_items(self.model_combo, sorted(model_map.keys()))

        # 填充模块下拉框（显示中文 label）
        self._set_combo_items(self.module_combo, [m["label"] for m in module_list])

        self._restore_filter_state(preserved_state)
        self._set_meta_loading_state(False)
        self.show_success(f"已{self._meta_request_label} {len(model_map)} 个型号，{len(module_list)} 个模块")

    def _on_meta_error(self, msg):
        self._set_meta_loading_state(False)
        self.show_error(f"{self._meta_request_label}元数据失败: {msg}")

    # ---------------------------------------------------- model -> version --

    def _on_model_changed(self, model_text):
        """型号变化时更新版本下拉框"""
        versions = self._model_map.get(model_text, [])
        self._set_combo_items(self.version_combo, versions)

    # ---------------------------------------------------- query / reset -----

    def _fill_today(self):
        from datetime import datetime
        now = datetime.now()
        self.start_dt.setText(now.strftime("%Y-%m-%d 00:00:00"))
        self.end_dt.setText(now.strftime("%Y-%m-%d 23:59:59"))

    def on_query(self):
        if not self._has_any_filter():
            self.show_warning("请填写筛选条件")
            return
        self.current_page = 1
        self._do_query(1)

    def on_refresh_meta(self):
        if self._meta_loading:
            self.show_info("筛选条件正在刷新，请稍候")
            return
        self._load_meta(force=True)

    def on_reset(self):
        self.sn_input.clear()
        self.model_combo.setCurrentIndex(0)
        self.version_combo.setCurrentIndex(0)
        self.module_combo.setCurrentIndex(0)
        self.error_code_input.clear()
        self.start_dt.clear()
        self.end_dt.clear()
        self._records = []
        self.result_table.setRowCount(0)
        self.current_page = 1
        self.total_pages = 1
        self.total_count = 0
        self._update_pagination()
        self._update_query_button_state()
        self.show_info("已重置筛选条件")

    def _do_query(self, page):
        self.current_page = page

        # 收集参数
        device_sn = self.sn_input.text().strip()
        device_model = self.model_combo.currentText().strip()
        device_identify = self.version_combo.currentText().strip()
        module_label = self.module_combo.currentText().strip()
        module_key = self._module_key_map.get(module_label, module_label)
        error_code = self.error_code_input.text().strip()
        start_time = self.start_dt.text().strip()
        end_time = self.end_dt.text().strip()

        self.show_progress(f"正在查询第 {page} 页...")
        self.query_btn.setEnabled(False)
        self.query_btn.setText("查询中...")
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.result_table.setRowCount(0)

        # 清理旧线程
        if hasattr(self, '_query_thread') and self._query_thread:
            try:
                if self._query_thread.isRunning():
                    self._query_thread.quit()
                    self._query_thread.wait(2000)
            except RuntimeError:
                pass
            self._query_thread = None

        thread = ErrorRecordQueryThread(
            page=page, size=self.per_page,
            device_sn=device_sn, device_model=device_model,
            device_identify=device_identify, module=module_key,
            error_code=error_code, start_time=start_time, end_time=end_time
        )
        thread.finished.connect(self._on_query_success)
        thread.error.connect(self._on_query_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self._query_thread = thread
        self.thread_mgr.add("query", thread)
        thread.start()

    def _on_query_success(self, records, current, pages, total):
        self._records = records
        self.current_page = current
        self.total_pages = pages
        self.total_count = total
        self._update_table()
        self._update_pagination()
        self._update_query_button_state()
        self.query_btn.setText("查询")
        has_data = total > 0
        self.export_csv_btn.setEnabled(has_data)
        self.export_json_btn.setEnabled(has_data)
        self.show_success(f"查询成功，共 {total} 条记录，第 {current}/{pages} 页")

    def _on_query_error(self, msg):
        self._update_query_button_state()
        self.query_btn.setText("查询")
        self._update_pagination()
        self.show_error(f"查询失败: {msg}")

    # ---------------------------------------------------- pagination --------

    def on_prev_page(self):
        if self.current_page > 1:
            self._do_query(self.current_page - 1)

    def on_next_page(self):
        if self.current_page < self.total_pages:
            self._do_query(self.current_page + 1)

    def _update_pagination(self):
        self.page_label.setText(f"[{self.current_page}/{self.total_pages}]")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)
        if self.total_count:
            self.total_label.setText(f"共 {self.total_count} 条")
        else:
            self.total_label.setText("")

    # ---------------------------------------------------- table -------------

    def _update_table(self):
        self.result_table.setRowCount(len(self._records))
        start_idx = (self.current_page - 1) * self.per_page + 1

        for row, rec in enumerate(self._records):
            # 行头显示递增序号
            seq_item = QTableWidgetItem(str(start_idx + row))
            seq_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setVerticalHeaderItem(row, seq_item)

            for col, (_, field, _, _) in enumerate(self.COLUMNS):
                value = rec.get(field, "") or ""
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.result_table.setItem(row, col, item)

        self.result_table.resizeRowsToContents()

    # ---------------------------------------------------- column resize -----

    def _on_column_resized(self, logical_index):
        if self._col_resize_timer:
            self._col_resize_timer.stop()
        self._col_resize_timer = QTimer()
        self._col_resize_timer.setSingleShot(True)
        self._col_resize_timer.timeout.connect(lambda: self._do_column_resize(logical_index))
        self._col_resize_timer.start(200)

    def _do_column_resize(self, logical_index):
        """用户手动拖拽列宽后，将差值均匀分配到其他列"""
        table_width = self.result_table.width()
        if table_width <= 0:
            return
        col_count = len(self.COLUMNS)
        current_total = sum(self.result_table.columnWidth(i) for i in range(col_count))
        diff = table_width - current_total
        if diff != 0:
            other_cols = [i for i in range(col_count) if i != logical_index]
            if other_cols:
                adj = diff / len(other_cols)
                for i in other_cols:
                    min_w = self.COLUMNS[i][3]
                    new_w = max(min_w, int(self.result_table.columnWidth(i) + adj))
                    self.result_table.setColumnWidth(i, new_w)

    def adjust_table_columns(self):
        """窗口缩放时按比例整体缩放各列，每列受最小宽度保护"""
        table_width = self.result_table.width()
        if table_width <= 0:
            return
        col_count = len(self.COLUMNS)
        current_total = sum(self.result_table.columnWidth(i) for i in range(col_count))
        if current_total <= 0 or current_total == table_width:
            return
        scale = table_width / current_total
        for i in range(col_count):
            min_w = self.COLUMNS[i][3]
            new_w = max(min_w, int(self.result_table.columnWidth(i) * scale))
            self.result_table.setColumnWidth(i, new_w)

    # ---------------------------------------------------- copy --------------

    def _on_cell_double_clicked(self, row, column):
        item = self.result_table.item(row, column)
        if column == 0:
            sn_item = self.result_table.item(row, column)
            if sn_item and sn_item.text().strip():
                model_item = self.result_table.item(row, 1)
                fallback_model = model_item.text().strip() if model_item else ""
                self._show_device_info_dialog(sn_item.text().strip(), fallback_model)
            return

        if item:
            self._copy_item_text(item, show_message=True)

    def _show_device_info_dialog(self, device_sn, fallback_model=""):
        self.show_progress(f"正在查询设备 {device_sn} 信息...")

        if hasattr(self, '_device_info_thread') and self._device_info_thread:
            try:
                if self._device_info_thread.isRunning():
                    self._device_info_thread.quit()
                    self._device_info_thread.wait(2000)
            except RuntimeError:
                pass
            self._device_info_thread = None

        thread = DeviceInfoQueryThread(device_sn, fallback_model=fallback_model)
        thread.finished.connect(self._on_device_info_success)
        thread.error.connect(self._on_device_info_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self._device_info_thread = thread
        self.thread_mgr.add("device_info", thread)
        thread.start()

    def _on_device_info_success(self, info):
        self._device_info_thread = None
        dialog = DeviceInfoDialog(info, self)
        dialog.exec_()

    def _on_device_info_error(self, msg):
        self._device_info_thread = None
        self.show_error(f"查询设备信息失败: {msg}")

    def _copy_item_text(self, item, show_message=False):
        text = item.text()
        if not text:
            return

        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

        if show_message:
            self.show_success(f"已复制: {text}", 2000)

    def _copy_selected(self):
        items = self.result_table.selectedItems()
        if items:
            self._copy_item_text(items[0])

    # ---------------------------------------------------- export -----------

    def _get_export_params(self):
        """收集当前筛选参数"""
        module_label = self.module_combo.currentText().strip()
        return {
            "device_sn":       self.sn_input.text().strip(),
            "device_model":    self.model_combo.currentText().strip(),
            "device_identify": self.version_combo.currentText().strip(),
            "module":          self._module_key_map.get(module_label, module_label),
            "error_code":      self.error_code_input.text().strip(),
            "start_time":      self.start_dt.text().strip(),
            "end_time":        self.end_dt.text().strip(),
        }

    def _confirm_large_export(self):
        """超过 1000 条时弹窗确认，返回 True 表示继续"""
        if self.total_count > 10000:
            result = show_question_box(
                self,
                "提示",
                f"当前筛选结果共 {self.total_count} 条数据，导出可能需要较长时间，是否继续？",
            )
            return result == QMessageBox.Yes
        return True

    def on_export_csv(self):
        if self.total_count == 0:
            self.show_warning("没有可导出的数据")
            return
        if not self._confirm_large_export():
            return

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存CSV文件",
            os.path.expanduser(f"~/错误记录_{ts}.csv"),
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.csv'):
            file_path += '.csv'

        self._start_full_export(file_path, mode='csv')

    def on_export_json(self):
        if self.total_count == 0:
            self.show_warning("没有可导出的数据")
            return
        if not self._confirm_large_export():
            return

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存JSON文件",
            os.path.expanduser(f"~/collect-dev-info_{ts}.json"),
            "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.json'):
            file_path += '.json'

        self._start_full_export(file_path, mode='json')

    def _start_full_export(self, file_path, mode):
        """启动全量数据拉取 + 导出线程，并显示进度弹窗"""
        dlg = ExportProgressDialog(self)
        self._export_status_lbl = dlg.status_label
        self._export_dlg = dlg

        thread = _FullExportThread(
            params=self._get_export_params(),
            total=self.total_count,
            per_page=self.per_page,
            file_path=file_path,
            mode=mode,
        )
        self._export_thread = thread
        thread.progress.connect(self._export_status_lbl.setText)
        thread.finished.connect(lambda msg: self._on_export_done(msg, dlg))
        thread.error.connect(lambda msg: self._on_export_error(msg, dlg))
        thread.finished.connect(lambda _: thread.deleteLater())

        def on_cancel():
            thread.cancel()
            try:
                thread.finished.disconnect()
                thread.error.disconnect()
            except Exception:
                pass

        dlg.cancel_requested.connect(on_cancel)
        thread.start()
        dlg.exec_()

    def _on_export_done(self, msg, dlg):
        dlg.accept()
        self.show_success(msg)

    def _on_export_error(self, msg, dlg):
        dlg.accept()
        self.show_error(f"导出失败: {msg}")

    # ---------------------------------------------------- cleanup -----------

    def refresh_theme(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.result_table, "TABLE")
        if hasattr(self, 'page_label'):
            self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, 'total_label'):
            self.total_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        if hasattr(self, 'prev_btn'):
            self._apply_icon_button_style(self.prev_btn)
        if hasattr(self, 'next_btn'):
            self._apply_icon_button_style(self.next_btn)

    def cleanup(self):
        if hasattr(self, '_query_thread') and self._query_thread:
            try:
                if self._query_thread.isRunning():
                    self._query_thread.quit()
                    self._query_thread.wait(2000)
            except RuntimeError:
                pass
        if hasattr(self, '_export_thread') and self._export_thread:
            try:
                self._export_thread.cancel()
                if self._export_thread.isRunning():
                    self._export_thread.quit()
                    self._export_thread.wait(1000)
            except RuntimeError:
                pass

    def fast_cleanup(self):
        if hasattr(self, '_query_thread') and self._query_thread:
            try:
                if self._query_thread.isRunning():
                    self._query_thread.quit()
                    self._query_thread.wait(300)
            except RuntimeError:
                pass
        if hasattr(self, '_export_thread') and self._export_thread:
            try:
                self._export_thread.cancel()
                if self._export_thread.isRunning():
                    self._export_thread.quit()
                    self._export_thread.wait(300)
            except RuntimeError:
                pass


class _FullExportThread(QThread):
    """全量拉取所有页数据并导出到文件"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, params, total, per_page, file_path, mode):
        super().__init__()
        self._params = params
        self._total = total
        self._per_page = per_page
        self._file_path = file_path
        self._mode = mode          # 'csv' or 'json'
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @staticmethod
    def _make_daemon_executor(max_workers):
        """创建使用守护线程的线程池，程序退出时不阻塞"""
        import threading
        from concurrent.futures import ThreadPoolExecutor as _TPE
        executor = _TPE(max_workers=max_workers,
                        thread_name_prefix="export_worker")
        # 将已创建的线程设为守护线程
        for t in executor._threads:
            t.daemon = True
        return executor

    def run(self):
        try:
            from query_tool.utils.error_record_api import _make_device_query, fetch_error_records
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # 先用一个实例拿第一页，确认总页数（同时预热 token 缓存）
            dq = _make_device_query()
            first_records, _, total_pages, _ = fetch_error_records(
                dq, page=1, size=self._per_page, **self._params
            )
            if self._cancelled:
                self.error.emit("已取消")
                return

            self.progress.emit(f"共 {total_pages} 页，正在并发拉取...")

            # 用字典按页码存结果，page=1 已拿到
            page_results = {1: first_records}

            if total_pages > 1:
                # 并发拉取剩余页，每个 future 用独立 dq 实例
                max_workers = min(10, total_pages - 1)

                def fetch_page(page):
                    dq_i = _make_device_query()
                    records, _, _, _ = fetch_error_records(
                        dq_i, page=page, size=self._per_page, **self._params
                    )
                    return page, records

                with self._make_daemon_executor(max_workers) as executor:
                    futures = {executor.submit(fetch_page, p): p for p in range(2, total_pages + 1)}
                    done_count = 1
                    for future in as_completed(futures):
                        if self._cancelled:
                            for f in futures:
                                f.cancel()
                            self.error.emit("已取消")
                            return
                        page, records = future.result()
                        page_results[page] = records
                        done_count += 1
                        self.progress.emit(f"已拉取 {done_count}/{total_pages} 页...")

            # 按页码顺序合并
            all_records = []
            for p in range(1, total_pages + 1):
                all_records.extend(page_results.get(p, []))

            self.progress.emit(f"数据拉取完成，共 {len(all_records)} 条，正在写入...")

            if self._mode == 'csv':
                self._write_csv(all_records)
            else:
                self._write_json(all_records)

        except Exception as e:
            from query_tool.utils.logger import logger
            logger.error(f"_FullExportThread 异常: {e}")
            self.error.emit(str(e))

    # ---- CSV ----
    def _write_csv(self, records):
        import csv
        headers = ["设备SN", "设备型号", "设备版本", "所属模块", "错误码", "错误描述", "触发时间", "上报时间"]
        fields  = ["deviceSn", "deviceModel", "deviceIdentify", "module", "errorCode", "errorMsg", "errorTime", "reportTime"]
        with open(self._file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for rec in records:
                writer.writerow([rec.get(k, "") or "" for k in fields])
        import os
        self.finished.emit(f"导出成功：{os.path.basename(self._file_path)}（共 {len(records)} 条）")

    # ---- JSON ----
    def _write_json(self, records):
        import json
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 去重 SN
        sns = list(dict.fromkeys(r.get("deviceSn", "") for r in records if r.get("deviceSn")))
        total_sns = len(sns)
        self.progress.emit(f"正在查询 {total_sns} 个设备密码...")

        sn_pwd = {}

        def query_pwd(sn):
            if self._cancelled:
                return sn, ""
            try:
                from query_tool.utils.error_record_api import _make_device_query
                dq_i = _make_device_query()
                info = dq_i.get_device_info(dev_sn=sn)
                recs = info.get('data', {}).get('records', [])
                if recs and not self._cancelled:
                    dev_id = recs[0].get('devId')
                    pwd = dq_i.get_cloud_password(dev_id) if dev_id else ""
                    return sn, pwd or ""
            except Exception:
                pass
            return sn, ""

        done = 0
        with self._make_daemon_executor(50) as executor:
            futures = {executor.submit(query_pwd, sn): sn for sn in sns}
            for future in as_completed(futures):
                if self._cancelled:
                    # 取消所有还未开始的 future
                    for f in futures:
                        f.cancel()
                    self.error.emit("已取消")
                    return
                sn, pwd = future.result()
                sn_pwd[sn] = pwd
                done += 1
                if done % 10 == 0 or done == total_sns:
                    self.progress.emit(f"查询密码中 {done}/{total_sns}...")

        self.progress.emit("正在写入 JSON...")
        json_records = []
        for sn in sns:  # sns 已去重，每个 SN 只写一条
            json_records.append({
                "firmware": "",
                "gatewayId": "",
                "sn": sn,
                "password": sn_pwd.get(sn, ""),
                "upgradeState": 0
            })

        import os
        with open(self._file_path, 'w', encoding='utf-8') as f:
            lines = [json.dumps(r, ensure_ascii=False) for r in json_records]
            f.write('{"RECORDS": [\n    ')
            f.write(',\n    '.join(lines))
            f.write('\n]}')

        self.finished.emit(f"导出成功：{os.path.basename(self._file_path)}（共 {len(json_records)} 条）")
