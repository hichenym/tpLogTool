"""
错误码记录查询页面
展示设备错误码上报记录，支持多条件筛选和分页
"""
import sys
import os

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QLineEdit, QComboBox,
    QFrame, QCompleter, QShortcut
)
from PyQt5.QtCore import Qt, QSize, QTimer, QStringListModel, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import ButtonManager, ThreadManager, StyleManager
from query_tool.utils.theme_manager import t
from query_tool.utils.error_record_api import MetaLoadThread, ErrorRecordQueryThread
from query_tool.widgets.custom_widgets import set_dark_title_bar


class _NoWheelComboBox(QComboBox):
    """禁用鼠标滚轮切换的可编辑下拉框"""
    def wheelEvent(self, event):
        event.ignore()


@register_page("记录", order=3, icon=":/icons/system/record.png")
class ErrorRecordPage(BasePage):
    """错误码记录查询页面"""

    # 表格列定义：(表头, 数据字段, 初始宽度, 最小宽度)
    COLUMNS = [
        ("设备SN",        "deviceSn",        160, 100),
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

    # ------------------------------------------------------------------ UI --

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        layout.addWidget(self._create_filter_group())
        layout.addWidget(self._create_result_group())

        self.main_buttons = self.btn_manager.create_group("main")
        self.main_buttons.add(self.query_btn)
        self.main_buttons.add(self.reset_btn)

    def _create_filter_group(self):
        group = QGroupBox("筛选条件")
        gl = QVBoxLayout(group)
        gl.setContentsMargins(10, 15, 10, 10)
        gl.setSpacing(6)

        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        self._filter_frame = frame

        fl = QVBoxLayout(frame)
        fl.setContentsMargins(10, 8, 10, 8)
        fl.setSpacing(6)

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

        self.start_dt = QLineEdit()
        self.start_dt.setPlaceholderText("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setFixedHeight(28)

        self.end_dt = QLineEdit()
        self.end_dt.setPlaceholderText("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setFixedHeight(28)

        self.query_btn = QPushButton("查询")
        self.query_btn.setIcon(QIcon(":/icons/common/search.png"))
        self.query_btn.setIconSize(QSize(16, 16))
        self.query_btn.setFixedHeight(28)
        self.query_btn.setStyleSheet("QPushButton { padding-left: 8px; padding-right: 8px; }")
        self.query_btn.clicked.connect(self.on_query)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.setIcon(QIcon(":/icons/common/clean.png"))
        self.reset_btn.setIconSize(QSize(16, 16))
        self.reset_btn.setFixedHeight(28)
        self.reset_btn.setStyleSheet("QPushButton { padding-left: 8px; padding-right: 8px; }")
        self.reset_btn.clicked.connect(self.on_reset)

        range_sep = QLabel("-")
        range_sep.setFixedWidth(10)
        range_sep.setAlignment(Qt.AlignCenter)
        range_sep.setStyleSheet("border: none;")

        today_btn = QPushButton("今")
        today_btn.setFixedHeight(28)
        today_btn.setStyleSheet("QPushButton { padding-left: 6px; padding-right: 6px; }")
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
        row2.addWidget(self.query_btn)
        row2.addSpacing(4)
        row2.addWidget(self.reset_btn)

        fl.addLayout(row1)
        fl.addLayout(row2)
        gl.addWidget(frame)

        # 型号变化时联动版本
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        return group

    def _create_result_group(self):
        group = QGroupBox("查询结果")
        gl = QVBoxLayout(group)
        gl.setContentsMargins(10, 15, 10, 10)
        gl.setSpacing(8)

        col_count = len(self.COLUMNS)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(col_count)
        self.result_table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self.result_table.setFocusPolicy(Qt.StrongFocus)
        self.result_table.setSelectionMode(QTableWidget.SingleSelection)
        self.result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setShowGrid(True)
        self.result_table.setFrameShape(QTableWidget.NoFrame)
        self.result_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.result_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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

        # 分页栏
        pager = QHBoxLayout()
        pager.setContentsMargins(0, 3, 0, 0)
        pager.setSpacing(3)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(QIcon(":/icons/common/ssy.png"))
        self.prev_btn.setIconSize(QSize(18, 18))
        self.prev_btn.setFixedSize(30, 22)
        self.prev_btn.setStyleSheet("QPushButton { padding: 0px; }")
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self.on_prev_page)

        self.page_label = QLabel("[0/0]")
        self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        self.page_label.setFixedHeight(22)
        self.page_label.setMinimumWidth(70)
        self.page_label.setAlignment(Qt.AlignCenter)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(QIcon(":/icons/common/xyy.png"))
        self.next_btn.setIconSize(QSize(18, 18))
        self.next_btn.setFixedSize(30, 22)
        self.next_btn.setStyleSheet("QPushButton { padding: 0px; }")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.on_next_page)

        self.total_label = QLabel("")
        self.total_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")
        self.total_label.setFixedHeight(22)
        self.total_label.setAlignment(Qt.AlignVCenter)

        self.export_csv_btn = QPushButton("导出CSV")
        self.export_csv_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_csv_btn.setIconSize(QSize(16, 16))
        self.export_csv_btn.setFixedHeight(28)
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self.on_export_csv)

        self.export_json_btn = QPushButton("导出JSON")
        self.export_json_btn.setIcon(QIcon(":/icons/common/export.png"))
        self.export_json_btn.setIconSize(QSize(16, 16))
        self.export_json_btn.setFixedHeight(28)
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
        lbl = QLabel(text)
        lbl.setFixedWidth(70)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl.setStyleSheet("border: none;")
        return lbl

    @staticmethod
    def _make_lineedit(placeholder):
        w = QLineEdit()
        w.setPlaceholderText(placeholder)
        w.setFixedHeight(28)
        return w

    @staticmethod
    def _make_combo(editable=False, placeholder=""):
        cb = _NoWheelComboBox()
        cb.setFixedHeight(28)
        cb.setFocusPolicy(Qt.StrongFocus)
        if editable:
            cb.setEditable(True)
            cb.setInsertPolicy(QComboBox.NoInsert)
            cb.lineEdit().setPlaceholderText(placeholder)
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
        if combo.completer():
            all_items = [combo.itemText(i) for i in range(combo.count())]
            combo.completer().setModel(QStringListModel(all_items))
        combo.blockSignals(False)

    # ---------------------------------------------------- page lifecycle ----

    def on_page_show(self):
        self.show_info("记录页面")
        self.adjust_table_columns()
        if not self._meta_loaded:
            self._load_meta()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_timer:
            self._resize_timer.stop()
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self.adjust_table_columns)
        self._resize_timer.start(150)

    # ---------------------------------------------------- meta loading ------

    def _load_meta(self):
        self.show_progress("正在加载型号和模块数据...")
        self.query_btn.setEnabled(False)

        thread = MetaLoadThread()
        thread.finished.connect(self._on_meta_loaded)
        thread.error.connect(self._on_meta_error)
        thread.finished.connect(lambda: thread.deleteLater())
        self.thread_mgr.add("meta", thread)
        thread.start()

    def _on_meta_loaded(self, model_map, module_list):
        self._model_map = model_map
        self._module_list = module_list
        self._module_key_map = {m["label"]: m["key"] for m in module_list}
        self._meta_loaded = True

        # 填充型号下拉框
        self._set_combo_items(self.model_combo, sorted(model_map.keys()))

        # 填充模块下拉框（显示中文 label）
        self._set_combo_items(self.module_combo, [m["label"] for m in module_list])

        self.query_btn.setEnabled(True)
        self.show_success(f"已加载 {len(model_map)} 个型号，{len(module_list)} 个模块")

    def _on_meta_error(self, msg):
        self.query_btn.setEnabled(True)
        self.show_error(f"加载元数据失败: {msg}")

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
        self.current_page = 1
        self._do_query(1)

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
        self.query_btn.setEnabled(True)
        self.query_btn.setText("查询")
        has_data = total > 0
        self.export_csv_btn.setEnabled(has_data)
        self.export_json_btn.setEnabled(has_data)
        self.show_success(f"查询成功，共 {total} 条记录，第 {current}/{pages} 页")

    def _on_query_error(self, msg):
        self.query_btn.setEnabled(True)
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

    def _copy_selected(self):
        items = self.result_table.selectedItems()
        if items:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(items[0].text())

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
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("提示")
            msg_box.setText(f"当前筛选结果共 {self.total_count} 条数据，导出可能需要较长时间，是否继续？")
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
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
            QTimer.singleShot(0, lambda: set_dark_title_bar(msg_box))
            return msg_box.exec_() == QMessageBox.Yes
        return True

    def on_export_csv(self):
        if self.total_count == 0:
            self.show_warning("没有可导出的数据")
            return
        if not self._confirm_large_export():
            return

        from PyQt5.QtWidgets import QFileDialog
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

        from PyQt5.QtWidgets import QFileDialog
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
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar
        from PyQt5.QtCore import Qt

        # 进度弹窗
        dlg = QDialog(self)
        dlg.setWindowTitle("正在导出")
        dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dlg.setFixedSize(360, 120)
        dlg.setModal(True)
        vl = QVBoxLayout(dlg)
        self._export_status_lbl = QLabel("正在拉取数据，请稍候...")
        self._export_status_lbl.setAlignment(Qt.AlignCenter)
        bar = QProgressBar()
        bar.setRange(0, 0)   # 不确定进度，滚动条
        cancel_btn = QPushButton("取消")
        vl.addWidget(self._export_status_lbl)
        vl.addWidget(bar)
        vl.addWidget(cancel_btn)
        self._export_dlg = dlg

        thread = _FullExportThread(
            params=self._get_export_params(),
            total=self.total_count,
            per_page=self.per_page,
            file_path=file_path,
            mode=mode,
        )
        self._export_thread = thread
        cancel_btn.clicked.connect(thread.cancel)
        cancel_btn.clicked.connect(dlg.reject)
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
            dlg.reject()

        cancel_btn.clicked.connect(on_cancel)
        thread.start()
        QTimer.singleShot(0, lambda: set_dark_title_bar(dlg))
        dlg.exec_()

    def _on_export_done(self, msg, dlg):
        dlg.accept()
        self.show_success(msg)

    def _on_export_error(self, msg, dlg):
        dlg.accept()
        self.show_error(f"导出失败: {msg}")

    # ---------------------------------------------------- cleanup -----------

    def refresh_theme(self):
        StyleManager.apply_to_widget(self.result_table, "TABLE")
        if hasattr(self, '_filter_frame'):
            self._filter_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        if hasattr(self, 'page_label'):
            self.page_label.setStyleSheet(f"color: {t('text_primary')}; font-size: 12px;")
        if hasattr(self, 'total_label'):
            self.total_label.setStyleSheet(f"color: {t('text_hint')}; font-size: 11px;")

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
