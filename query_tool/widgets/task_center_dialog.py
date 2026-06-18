from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from .adaptive_dialog import AdaptiveDialog
from .custom_widgets import set_dark_title_bar
from query_tool.ui import (
    BodyLabel,
    CheckBox,
    ElevatedCardWidget,
    PushButton,
    QFLUENT_WIDGETS_AVAILABLE,
    SubtitleLabel,
    TableWidget,
)
from query_tool.utils.task_center import (
    TASK_STATUS_CANCELED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PAUSED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    cancel_task,
    continue_task,
    delete_task,
    list_tasks,
    mark_task_paused,
    reset_task_for_execute,
    start_task_process,
)
from query_tool.utils import StyleManager
from query_tool.utils.theme_manager import t, theme_manager


class TaskCenterDialog(AdaptiveDialog):
    """Display and control persisted background tasks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_tasks)
        self._tasks_by_id = {}
        self._selected_task_ids: set[str] = set()
        self.resize_timer = None
        self._adjusting_columns = False
        self._column_min_widths = {
            1: 180,
            2: 145,
            3: 85,
            4: 95,
            5: 125,
            6: 220,
        }
        self.setWindowTitle("后台任务")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        theme_manager.theme_changed.connect(self.refresh_theme)
        self.destroyed.connect(self._disconnect_theme)
        self.init_ui()
        self.refresh_tasks()
        self._refresh_timer.start(1000)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
        QTimer.singleShot(0, self.apply_column_widths)

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self.refresh_theme)
        except Exception:
            pass

    @staticmethod
    def _apply_dialog_title_style(label):
        label.setStyleSheet(f"color: {t('status_info')}; border: none;")

    @staticmethod
    def _apply_summary_style(label):
        label.setStyleSheet(f"color: {t('text_hint')}; font-size: 12px; border: none;")

    @staticmethod
    def _apply_card_title_style(label):
        label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600; border: none;")

    def _apply_secondary_button_style(self, button):
        if not QFLUENT_WIDGETS_AVAILABLE:
            button.setStyleSheet(StyleManager.get_ACTION_BUTTON())

    def _apply_card_style(self, card):
        if QFLUENT_WIDGETS_AVAILABLE:
            card.setStyleSheet("")
            return
        card.setStyleSheet(
            f"""
            #taskCenterCard {{
                border: 1px solid {t('border')};
                border-radius: 6px;
                background-color: transparent;
            }}
            """
        )

    def _apply_table_style(self):
        if not QFLUENT_WIDGETS_AVAILABLE:
            StyleManager.apply_to_widget(self.task_table, "TABLE")

    @staticmethod
    def _apply_transparent_container_style(widget):
        widget.setAttribute(Qt.WA_StyledBackground, True)
        widget.setStyleSheet("background-color: transparent; border: none;")

    def _create_checkbox_cell_widget(self, checkbox):
        checkbox_widget = QWidget()
        self._apply_transparent_container_style(checkbox_widget)
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.addWidget(checkbox)
        return checkbox_widget

    def refresh_theme(self):
        self._apply_dialog_title_style(self.title_label)
        self._apply_summary_style(self.summary_label)
        self._apply_card_title_style(self.task_group_title)
        self._apply_card_style(self.task_group)
        self._apply_table_style()
        for button in (
            self.pause_btn,
            self.continue_btn,
            self.execute_btn,
            self.cancel_btn,
            self.delete_btn,
        ):
            self._apply_secondary_button_style(button)
        set_dark_title_bar(self)

    def init_ui(self):
        layout = self.init_dialog_layout(
            (1040, 460),
            min_size=(760, 320),
            layout_margins=(18, 18, 18, 18),
            spacing=12,
        )

        header_layout = QHBoxLayout()
        self.title_label = SubtitleLabel("后台任务列表")
        self.summary_label = BodyLabel("加载中...")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.summary_label)
        layout.addLayout(header_layout)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        self.select_all_checkbox = CheckBox("全选")
        self.select_all_checkbox.setTristate(False)
        self.select_all_checkbox.stateChanged.connect(self.on_select_all_changed)

        self.pause_btn = self._create_toolbar_button("暂停", ":/icons/common/cancel.png", self.on_pause_clicked)
        self.continue_btn = self._create_toolbar_button("继续", ":/icons/common/ok.png", self.on_continue_clicked)
        self.execute_btn = self._create_toolbar_button("执行", ":/icons/common/run.png", self.on_execute_clicked)
        self.cancel_btn = self._create_toolbar_button("取消", ":/icons/common/clean.png", self.on_cancel_clicked)
        self.delete_btn = self._create_toolbar_button("删除", ":/icons/common/delete.png", self.on_delete_clicked)

        toolbar_layout.addWidget(self.select_all_checkbox)
        toolbar_layout.addWidget(self.pause_btn)
        toolbar_layout.addWidget(self.continue_btn)
        toolbar_layout.addWidget(self.execute_btn)
        toolbar_layout.addWidget(self.cancel_btn)
        toolbar_layout.addWidget(self.delete_btn)
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        self.task_group = ElevatedCardWidget(self)
        self.task_group.setObjectName("taskCenterCard")
        group_layout = QVBoxLayout(self.task_group)
        group_layout.setContentsMargins(16, 16, 16, 16)
        group_layout.setSpacing(10)
        self.task_group_title = BodyLabel("任务信息")
        group_layout.addWidget(self.task_group_title)

        self.task_table = TableWidget()
        self.task_table.setColumnCount(7)
        self.task_table.setHorizontalHeaderLabels(
            ["选择", "任务名称", "开始时间", "状态", "进度", "结果目录", "执行详情"]
        )
        self.task_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.task_table.setSelectionMode(TableWidget.SingleSelection)
        self.task_table.setSelectionBehavior(TableWidget.SelectRows)
        self.task_table.setFocusPolicy(Qt.StrongFocus)
        self.task_table.setWordWrap(False)
        self.task_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.task_table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        header = self.task_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        for col in range(1, 6):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        header.sectionResized.connect(self.on_column_resized)
        self.task_table.setColumnWidth(0, 50)
        self.apply_column_widths()
        group_layout.addWidget(self.task_table)
        layout.addWidget(self.task_group)
        self.update_action_buttons()
        self.refresh_theme()

    def _create_toolbar_button(self, text: str, icon_path: str, handler):
        button = PushButton(text)
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(16, 16))
        button.setMinimumWidth(96)
        button.clicked.connect(handler)
        self._apply_secondary_button_style(button)
        return button

    def refresh_tasks(self):
        tasks = list_tasks()
        self._tasks_by_id = {str(task.get("task_id", "")): task for task in tasks}
        valid_task_ids = {task_id for task_id in self._tasks_by_id if task_id}
        self._selected_task_ids.intersection_update(valid_task_ids)
        total = len(tasks)
        self.task_table.setRowCount(total)

        running_count = 0
        for row, task in enumerate(tasks):
            status_text = str(task.get("status", ""))
            if status_text in (TASK_STATUS_PENDING, TASK_STATUS_RUNNING):
                running_count += 1

            self.task_table.setVerticalHeaderItem(row, QTableWidgetItem(str(total - row)))

            checkbox = CheckBox()
            task_id = str(task.get("task_id", "")).strip()
            checkbox.setProperty("task_id", task_id)
            checkbox.setChecked(task_id in self._selected_task_ids)
            checkbox.stateChanged.connect(lambda state, current_task_id=task_id: self.on_task_checkbox_changed(current_task_id, state))
            checkbox_widget = self._create_checkbox_cell_widget(checkbox)
            self.task_table.setCellWidget(row, 0, checkbox_widget)

            progress_current = int(task.get("progress_current", 0) or 0)
            progress_total = int(task.get("progress_total", 0) or 0)
            progress_display = "-" if progress_total <= 0 else f"{min(progress_current, progress_total)}/{progress_total}"

            detail = task.get("progress_text", "") or task.get("last_error", "")
            values = [
                task.get("name", ""),
                self._format_datetime(task.get("started_at") or task.get("created_at", "")),
                self._format_status(status_text),
                progress_display,
                task.get("result_dir", ""),
                detail,
            ]
            for col_offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value or ""))
                if col_offset == 3:
                    item.setData(Qt.ForegroundRole, self._status_color(status_text))
                    item.setTextAlignment(Qt.AlignCenter)
                self.task_table.setItem(row, col_offset, item)

        self.summary_label.setText(f"运行中 {running_count} 个，总任务 {total} 个")
        self.update_select_all_state()
        self.apply_column_widths()
        self.update_action_buttons()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_column_widths()

    def on_column_resized(self, section: int, _old_size: int, new_size: int):
        if self._adjusting_columns or section <= 0 or section >= 6:
            return
        if self.resize_timer is not None:
            self.resize_timer.stop()
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(lambda s=section: self._do_column_resize(s))
        self.resize_timer.start(120)

    def apply_column_widths(self):
        available = self.task_table.viewport().width()
        if available <= 0:
            return
        fixed_width = self.task_table.columnWidth(0)
        stretch_width = max(self.task_table.columnWidth(6), self._column_min_widths[6])
        remaining = max(available - fixed_width - stretch_width, sum(self._column_min_widths[col] for col in range(1, 6)))
        current_widths = {
            col: max(self.task_table.columnWidth(col), self._column_min_widths[col])
            for col in range(1, 6)
        }
        current_total = sum(current_widths.values()) or 1
        self._adjusting_columns = True
        try:
            assigned = 0
            for col in range(1, 6):
                if col == 5:
                    width = max(self._column_min_widths[col], remaining - assigned)
                else:
                    width = max(
                        self._column_min_widths[col],
                        int(remaining * current_widths[col] / current_total),
                    )
                    assigned += width
                self.task_table.setColumnWidth(col, width)
        finally:
            self._adjusting_columns = False

    def _do_column_resize(self, logical_index: int):
        available = self.task_table.viewport().width()
        if available <= 0:
            return
        fixed_width = self.task_table.columnWidth(0)
        stretch_width = max(self.task_table.columnWidth(6), self._column_min_widths[6])
        target_total = max(available - fixed_width - stretch_width, sum(self._column_min_widths[col] for col in range(1, 6)))
        current_total = sum(self.task_table.columnWidth(col) for col in range(1, 6))
        diff = target_total - current_total
        if diff == 0 or logical_index not in range(1, 6):
            return

        other_cols = [col for col in range(1, 6) if col != logical_index]
        if not other_cols:
            return

        self._adjusting_columns = True
        try:
            if diff < 0:
                shrinkable_total = sum(
                    max(0, self.task_table.columnWidth(col) - self._column_min_widths[col])
                    for col in other_cols
                )
                if shrinkable_total <= 0:
                    max_width = self.task_table.columnWidth(logical_index) + diff
                    self.task_table.setColumnWidth(
                        logical_index,
                        max(self._column_min_widths[logical_index], max_width),
                    )
                    diff = target_total - sum(self.task_table.columnWidth(col) for col in range(1, 6))
            for index, col in enumerate(other_cols):
                current_width = self.task_table.columnWidth(col)
                if index == len(other_cols) - 1:
                    new_width = max(self._column_min_widths[col], current_width + diff)
                else:
                    share = int(diff / (len(other_cols) - index))
                    if diff < 0:
                        shrinkable = max(0, current_width - self._column_min_widths[col])
                        share = -min(abs(share), shrinkable)
                    new_width = max(self._column_min_widths[col], current_width + share)
                    diff -= (new_width - current_width)
                self.task_table.setColumnWidth(col, new_width)
        finally:
            self._adjusting_columns = False

    def selected_task_ids(self) -> list[str]:
        task_ids: list[str] = []
        for row in range(self.task_table.rowCount()):
            widget = self.task_table.cellWidget(row, 0)
            checkbox = widget.findChild(CheckBox) if widget is not None else None
            if checkbox is None:
                continue
            task_id = str(checkbox.property("task_id") or "").strip()
            if task_id and task_id in self._selected_task_ids:
                task_ids.append(task_id)
        return task_ids

    def on_task_checkbox_changed(self, task_id: str, state: int):
        if not task_id:
            return
        if state == Qt.Checked:
            self._selected_task_ids.add(task_id)
        else:
            self._selected_task_ids.discard(task_id)
        self.update_select_all_state()

    def update_select_all_state(self, *_args):
        total = self.task_table.rowCount()
        if total == 0:
            self._selected_task_ids.clear()
            self.select_all_checkbox.blockSignals(True)
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
            self.select_all_checkbox.blockSignals(False)
            self.update_action_buttons()
            return

        visible_task_ids: list[str] = []
        for row in range(total):
            widget = self.task_table.cellWidget(row, 0)
            checkbox = widget.findChild(CheckBox) if widget is not None else None
            if checkbox is None:
                continue
            task_id = str(checkbox.property("task_id") or "").strip()
            if task_id:
                visible_task_ids.append(task_id)

        checked = sum(1 for task_id in visible_task_ids if task_id in self._selected_task_ids)

        self.select_all_checkbox.blockSignals(True)
        if checked == 0:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        elif checked == len(visible_task_ids):
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.PartiallyChecked)
        self.select_all_checkbox.blockSignals(False)
        self.update_action_buttons()

    def on_select_all_changed(self, state):
        if state not in (Qt.Checked, Qt.Unchecked):
            return
        visible_task_ids: list[str] = []
        for row in range(self.task_table.rowCount()):
            widget = self.task_table.cellWidget(row, 0)
            checkbox = widget.findChild(CheckBox) if widget is not None else None
            if checkbox is None:
                continue
            task_id = str(checkbox.property("task_id") or "").strip()
            if task_id:
                visible_task_ids.append(task_id)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(state == Qt.Checked)
                checkbox.blockSignals(False)
        if state == Qt.Checked:
            self._selected_task_ids.update(visible_task_ids)
        else:
            for task_id in visible_task_ids:
                self._selected_task_ids.discard(task_id)
        self.update_select_all_state()

    def _ensure_selection(self) -> list[str]:
        task_ids = self.selected_task_ids()
        if not task_ids:
            return []
        return task_ids

    def selected_tasks(self) -> list[dict]:
        tasks = []
        for task_id in self.selected_task_ids():
            task = self._tasks_by_id.get(task_id)
            if task:
                tasks.append(task)
        return tasks

    def update_action_buttons(self):
        selected_tasks = self.selected_tasks()
        has_selection = bool(selected_tasks)
        statuses = [str(task.get("status", "")) for task in selected_tasks]

        has_running = any(status == TASK_STATUS_RUNNING for status in statuses)
        has_paused = any(status == TASK_STATUS_PAUSED for status in statuses)
        has_executable = any(
            status in (TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_CANCELED)
            for status in statuses
        )
        has_cancelable = any(status in (TASK_STATUS_RUNNING, TASK_STATUS_PAUSED) for status in statuses)
        selection_is_all = has_selection and len(selected_tasks) == len(self._tasks_by_id)
        all_selected_mixed_running = selection_is_all and has_running and any(
            status != TASK_STATUS_RUNNING for status in statuses
        )

        self.pause_btn.setEnabled(has_selection and has_running)
        self.continue_btn.setEnabled(has_selection and has_paused)
        self.execute_btn.setEnabled(has_selection and has_executable)
        self.cancel_btn.setEnabled(has_selection and has_cancelable and not all_selected_mixed_running)
        self.delete_btn.setEnabled(has_selection and not has_running and not all_selected_mixed_running)

    def on_pause_clicked(self):
        tasks = [task for task in self.selected_tasks() if task.get("status") == TASK_STATUS_RUNNING]
        if not tasks:
            return
        for task in tasks:
            mark_task_paused(task.get("task_id", ""), stop_process=True)
        self.refresh_tasks()
        self._refresh_parent_indicator()

    def on_continue_clicked(self):
        tasks = [task for task in self.selected_tasks() if task.get("status") == TASK_STATUS_PAUSED]
        if not tasks:
            return
        for task in tasks:
            continue_task(task.get("task_id", ""))
        self.refresh_tasks()
        self._refresh_parent_indicator()

    def on_execute_clicked(self):
        tasks = [
            task for task in self.selected_tasks()
            if task.get("status") in (TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_CANCELED)
        ]
        if not tasks:
            return
        for task_info in tasks:
            task = reset_task_for_execute(task_info.get("task_id", ""))
            if task:
                start_task_process(task.get("task_id", ""))
        self.refresh_tasks()
        self._refresh_parent_indicator()

    def on_cancel_clicked(self):
        tasks = [
            task for task in self.selected_tasks()
            if task.get("status") in (TASK_STATUS_RUNNING, TASK_STATUS_PAUSED)
        ]
        if not tasks:
            return
        for task in tasks:
            cancel_task(task.get("task_id", ""))
        self.refresh_tasks()
        self._refresh_parent_indicator()

    def on_delete_clicked(self):
        tasks = [
            task for task in self.selected_tasks()
            if task.get("status") not in (TASK_STATUS_RUNNING,)
        ]
        if not tasks:
            return
        changed = False
        for task in tasks:
            if delete_task(task.get("task_id", "")):
                self._selected_task_ids.discard(str(task.get("task_id", "")).strip())
                changed = True
        if changed:
            self.refresh_tasks()
            self._refresh_parent_indicator()

    def _refresh_parent_indicator(self):
        if self.parent() and hasattr(self.parent(), "refresh_running_task_indicator"):
            self.parent().refresh_running_task_indicator()

    def on_cell_double_clicked(self, row: int, column: int):
        if column != 5:
            return
        item = self.task_table.item(row, column)
        if not item:
            return
        path = item.text().strip()
        if not path or not os.path.isdir(path):
            return
        try:
            os.startfile(path)
        except Exception:
            pass

    @staticmethod
    def _format_status(status: str) -> str:
        mapping = {
            TASK_STATUS_PENDING: "等待中",
            TASK_STATUS_RUNNING: "进行中",
            TASK_STATUS_PAUSED: "暂停",
            TASK_STATUS_COMPLETED: "已完成",
            TASK_STATUS_FAILED: "失败",
            TASK_STATUS_CANCELED: "已取消",
        }
        return mapping.get(status, status or "-")

    @staticmethod
    def _format_datetime(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.replace("T", " ")

    @staticmethod
    def _status_color(status: str):
        mapping = {
            TASK_STATUS_PENDING: QColor(t("status_pending")),
            TASK_STATUS_RUNNING: QColor(t("status_info")),
            TASK_STATUS_PAUSED: QColor(t("status_pending")),
            TASK_STATUS_COMPLETED: QColor(t("status_online")),
            TASK_STATUS_FAILED: QColor(t("status_offline")),
            TASK_STATUS_CANCELED: QColor(t("text_hint")),
        }
        return mapping.get(status, QColor(t("text_hint")))
