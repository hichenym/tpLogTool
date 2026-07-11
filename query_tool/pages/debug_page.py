"""
设备调试页面
提供 Seetong 登录、设备登录和命令交互功能
"""
from datetime import datetime
from pathlib import Path
import time

from PyQt5.QtCore import QEvent, QMetaObject, QMimeData, QPoint, QRect, QSize, QThread, QTimer, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QDrag, QIcon, QImage, QKeySequence, QPixmap, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMenu,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage
from .page_registry import register_page
from query_tool.utils import StyleManager, config_manager, get_account_config, get_seetong_account_config
from query_tool.utils.theme_manager import t
from query_tool.utils.siot_debug import (
    DEFAULT_COMMAND_TIMEOUT_MS,
    SiotDebugWorker,
    is_getsystemcfg_command,
    is_startlogp2p_command,
    is_syscmd_family_command,
    parse_startlogp2p_level,
)
from query_tool.widgets.adaptive_dialog import AdaptiveDialog
from query_tool.widgets.custom_widgets import prompt_configure_account, set_dark_title_bar


class FlowLayout(QLayout):
    """支持自动换行的流式布局。"""

    def __init__(self, parent=None, margin=0, h_spacing=4, v_spacing=4):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        margins = self.contentsMargins()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def horizontalSpacing(self):
        return self._h_spacing

    def verticalSpacing(self):
        return self._v_spacing

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            space_x = self.horizontalSpacing()
            space_y = self.verticalSpacing()
            hint = item.sizeHint()
            next_x = x + hint.width() + space_x

            if line_height > 0 and next_x - space_x > effective_rect.right() + 1:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + hint.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))

            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom


class HistoryLineEdit(QLineEdit):
    """支持上下键切换历史命令的输入框。"""

    history_prev_requested = pyqtSignal()
    history_next_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.history_prev_requested.emit()
            return
        if event.key() == Qt.Key_Down:
            self.history_next_requested.emit()
            return
        super().keyPressEvent(event)


class PathDisplayLabel(QLabel):
    """支持双击打开目录的路径标签。"""

    double_clicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class NoWheelComboBox(QComboBox):
    """禁用滚轮切换，避免误操作。"""

    def wheelEvent(self, event):
        event.ignore()


class DraggableShortcutButton(QPushButton):
    """支持拖拽排序的快捷按钮。"""

    reorder_requested = pyqtSignal(str, str)

    MIME_TYPE = "application/x-tplogtool-shortcut"

    def __init__(self, command: str, parent=None):
        super().__init__(command, parent)
        self.command = command
        self._drag_start_pos = None
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(self.MIME_TYPE, self.command.encode("utf-8"))
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)
        self._drag_start_pos = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            dragged_command = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8", errors="ignore")
            if dragged_command and dragged_command != self.command:
                event.acceptProposedAction()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            dragged_command = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8", errors="ignore")
            if dragged_command and dragged_command != self.command:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        dragged_command = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8", errors="ignore")
        if not dragged_command or dragged_command == self.command:
            event.ignore()
            return

        self.reorder_requested.emit(dragged_command, self.command)
        event.acceptProposedAction()


class HistorySuggestionPopup(QFrame):
    """璋冭瘯鍛戒护鍘嗗彶鍊欓€夊脊灞傘€?"""

    command_clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    MAX_VISIBLE_ITEMS = 5
    MIN_WIDTH = 140
    MAX_WIDTH = 420
    HORIZONTAL_PADDING = 22
    VERTICAL_PADDING = 6

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("historySuggestionPopup")
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self.list_widget = QListWidget(self)
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list_widget.setTextElideMode(Qt.ElideMiddle)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemActivated.connect(self._on_item_clicked)
        self.list_widget.currentRowChanged.connect(self._refresh_row_styles)
        layout.addWidget(self.list_widget)

        self.refresh_theme()
        self.hide()

    def refresh_theme(self):
        self.setStyleSheet(
            f"""
            QFrame#historySuggestionPopup {{
                background-color: {t('bg_mid')};
                border: 1px solid {t('border')};
                border-radius: 4px;
            }}
            QListWidget {{
                background-color: transparent;
                color: {t('text_primary')};
                border: none;
                outline: none;
                padding: 2px;
                show-decoration-selected: 0;
            }}
            QListWidget::item {{
                padding: 0px;
                margin: 0px;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: transparent;
                color: {t('text_primary')};
                padding: 0px;
                margin: 0px;
                border: none;
            }}
            """
        )
        self._refresh_row_styles()

    def set_suggestions(self, suggestions):
        self.list_widget.clear()
        for command in suggestions:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, command)
            self.list_widget.addItem(item)
            row_widget = self._create_row_widget(command, item)
            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.setItemWidget(item, row_widget)
        self.list_widget.setCurrentRow(-1)
        self.list_widget.clearSelection()
        self._refresh_row_styles()

    def current_value(self):
        if not self.has_active_selection():
            return ""
        item = self.list_widget.currentItem()
        return self._item_command(item)

    def has_suggestions(self):
        return self.list_widget.count() > 0

    def has_active_selection(self):
        return self.list_widget.currentItem() is not None and self.list_widget.currentRow() >= 0

    def select_next(self):
        count = self.list_widget.count()
        if count <= 0:
            return
        current_row = self.list_widget.currentRow()
        next_row = 0 if current_row < 0 else min(count - 1, current_row + 1)
        next_item = self.list_widget.item(next_row)
        self.list_widget.setCurrentRow(next_row)
        if next_item is not None:
            self.list_widget.setCurrentItem(next_item)
            self.list_widget.scrollToItem(next_item)
        self._refresh_row_styles()

    def select_prev(self):
        count = self.list_widget.count()
        if count <= 0:
            return
        current_row = self.list_widget.currentRow()
        prev_row = count - 1 if current_row < 0 else max(0, current_row - 1)
        prev_item = self.list_widget.item(prev_row)
        self.list_widget.setCurrentRow(prev_row)
        if prev_item is not None:
            self.list_widget.setCurrentItem(prev_item)
            self.list_widget.scrollToItem(prev_item)
        self._refresh_row_styles()

    def show_popup(self, anchor_pos: QPoint, width_hint: int):
        if not self.has_suggestions():
            self.hide()
            return

        popup_size = self._popup_size(width_hint)
        popup_width = popup_size.width()
        popup_height = popup_size.height()
        parent_widget = self.parentWidget()
        x = anchor_pos.x()
        y = anchor_pos.y()
        if parent_widget is not None:
            max_x = max(4, parent_widget.width() - popup_width - 4)
            x = max(4, min(x, max_x))
            if y + popup_height > parent_widget.height() - 4:
                y = max(4, anchor_pos.y() - popup_height - 6)

        self.resize(popup_width, popup_height)
        self.move(x, y)
        self.show()
        self.raise_()

    def _popup_size(self, width_hint: int) -> QSize:
        row_height = self.list_widget.sizeHintForRow(0)
        if row_height <= 0:
            row_height = max(self.list_widget.fontMetrics().height() + 6, 22)
        visible_rows = min(self.list_widget.count(), self.MAX_VISIBLE_ITEMS)
        max_text_width = 0
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item is None:
                continue
            row_widget = self.list_widget.itemWidget(item)
            if row_widget is not None:
                max_text_width = max(max_text_width, row_widget.sizeHint().width())
            else:
                max_text_width = max(max_text_width, self.list_widget.fontMetrics().horizontalAdvance(self._item_command(item)))

        popup_width = max_text_width + self.HORIZONTAL_PADDING
        popup_width = max(self.MIN_WIDTH, popup_width)
        popup_width = min(popup_width, int(width_hint or self.MAX_WIDTH), self.MAX_WIDTH)
        popup_height = row_height * visible_rows + self.VERTICAL_PADDING
        return QSize(popup_width, popup_height)

    def _on_item_clicked(self, item):
        if item is not None:
            self.list_widget.setCurrentItem(item)
            self.command_clicked.emit(self._item_command(item))

    def _create_row_widget(self, command, item):
        row_widget = HistorySuggestionRowWidget(command, self.list_widget)
        row_widget.command_clicked.connect(lambda _cmd, list_item=item: self._on_row_command_clicked(list_item))
        row_widget.delete_requested.connect(lambda cmd: self.delete_requested.emit(cmd))
        return row_widget

    def _on_row_command_clicked(self, item):
        if item is not None:
            self.list_widget.setCurrentItem(item)
            self.command_clicked.emit(self._item_command(item))

    def _refresh_row_styles(self, _row=None):
        current_item = self.list_widget.currentItem()
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            row_widget = self.list_widget.itemWidget(item)
            if row_widget is not None:
                row_widget.refresh_theme(selected=item is current_item)

    @staticmethod
    def _item_command(item):
        if item is None:
            return ""
        return item.data(Qt.UserRole) or item.text() or ""


class HistorySuggestionRowWidget(QWidget):
    """鍘嗗彶鍛戒护鍊欓€夎锛屾敮鎸侀€夋嫨鍜屽垹闄ゃ€?"""

    command_clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, command: str, parent=None):
        super().__init__(parent)
        self.command = command
        self.setObjectName("historySuggestionRow")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.command_button = QPushButton(command, self)
        self.command_button.setObjectName("historySuggestionCommandButton")
        self.command_button.setFocusPolicy(Qt.NoFocus)
        self.command_button.setFlat(True)
        self.command_button.clicked.connect(self._emit_command_clicked)

        self.delete_button = QPushButton("x", self)
        self.delete_button.setObjectName("historySuggestionDeleteButton")
        self.delete_button.setFocusPolicy(Qt.NoFocus)
        self.delete_button.setFixedSize(18, 18)
        self.delete_button.setToolTip("Delete history command")
        self.delete_button.clicked.connect(self._emit_delete_requested)

        layout.addWidget(self.command_button, 1)
        layout.addWidget(self.delete_button, 0)

        self.refresh_theme(selected=False)

    def refresh_theme(self, selected=False):
        row_background = t("selection_bg") if selected else "transparent"
        delete_hover_background = t("bg_hover") if not selected else t("border")
        self.setStyleSheet(
            f"""
            QWidget#historySuggestionRow {{
                background-color: {row_background};
                border: none;
                border-radius: 3px;
            }}
            QPushButton#historySuggestionCommandButton {{
                border: none;
                background-color: {row_background};
                color: {t('text_primary')};
                padding: 0px;
                margin: 0px;
                text-align: left;
            }}
            QPushButton#historySuggestionCommandButton:hover {{
                background-color: {row_background};
            }}
            QPushButton#historySuggestionCommandButton:pressed {{
                background-color: {row_background};
            }}
            QPushButton#historySuggestionDeleteButton {{
                border: none;
                background-color: {row_background};
                color: {t('text_hint')};
                padding: 0px;
                margin: 0px;
                text-align: center;
                font-weight: bold;
                border-radius: 9px;
            }}
            QPushButton#historySuggestionDeleteButton:hover {{
                color: {t('status_offline')};
                background-color: {delete_hover_background};
            }}
            QPushButton#historySuggestionDeleteButton:pressed {{
                background-color: {delete_hover_background};
            }}
            """
        )

    def _emit_command_clicked(self):
        self.command_clicked.emit(self.command)

    def _emit_delete_requested(self):
        self.delete_requested.emit(self.command)


class DebugConsoleEdit(QTextEdit):
    """支持在交互区直接输入并发送命令的控制台文本框。"""

    MAX_ENTRIES = 3000
    MAX_STREAM_LOG_BLOCKS = 1000

    command_submitted = pyqtSignal(str)
    history_prev_requested = pyqtSignal()
    history_next_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    input_text_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._input_enabled = False
        self._input_locked = False
        self._prompt_text = "~ # "
        self._input_prompt_start = 0
        self._input_start = 0
        self._show_timestamps = True
        self._entries = []
        self._pressed_in_input_line = False
        self._browse_mode = False
        self._visible_cursor_width = 2
        self.setAcceptRichText(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setPlaceholderText("登录后可直接输入命令，回车发送指令...")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.copyAvailable.connect(self._auto_copy_selection)
        self.selectionChanged.connect(self._on_selection_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setCursorWidth(self._visible_cursor_width)

    def set_input_enabled(self, enabled: bool):
        self._input_enabled = enabled
        self.viewport().setCursor(Qt.IBeamCursor if enabled else Qt.ArrowCursor)
        if not enabled:
            self._browse_mode = False
        self._rebuild_document()

    def set_input_locked(self, locked: bool):
        self._input_locked = locked
        if locked:
            self._browse_mode = False
        if self._input_enabled:
            self._rebuild_document()

    def set_input_locked_quietly(self, locked: bool):
        self._input_locked = locked
        if locked:
            self._browse_mode = False
            self._hide_input_cursor()
        else:
            self._show_input_cursor()

    def clear_console(self):
        self._entries = []
        self.clear()
        self._input_prompt_start = 0
        self._input_start = 0
        self._browse_mode = False
        if self._input_enabled:
            self._rebuild_document()

    def set_show_timestamps(self, visible: bool):
        visible = bool(visible)
        if self._show_timestamps == visible:
            return
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()
        self._show_timestamps = visible
        self._rebuild_document()
        self.verticalScrollBar().setValue(v_scroll)
        self.horizontalScrollBar().setValue(h_scroll)

    def append_message(self, message: str, color: str = None, label: str = ""):
        color_role = self._infer_color_role(color)
        for line in (message or "").splitlines() or [""]:
            self._entries.append(
                {
                    "timestamp": datetime.now(),
                    "text": line,
                    "color": color,
                    "color_role": color_role,
                    "label": label,
                }
            )
        self._trim_entries()
        self._rebuild_document_with_scroll_restore()

    def append_command(self, command: str):
        self._entries.append(
            {
                "timestamp": datetime.now(),
                "text": command or "",
                "color_role": "status_info",
                "kind": "command",
            }
        )
        self._trim_entries()
        self._rebuild_document_with_scroll_restore()

    def commit_command_submission(self, command: str):
        """一次重绘内完成命令回显和输入锁定，减少回车时的顿感。"""
        self._entries.append(
            {
                "timestamp": datetime.now(),
                "text": command or "",
                "color_role": "status_info",
                "kind": "command",
            }
        )
        self._trim_entries()
        self._input_locked = True
        self._browse_mode = False
        self._rebuild_document_with_scroll_restore()

    def commit_console_submission_live(self, command: str):
        """控制台直接回车时，原地追加命令和新提示行，避免整页重绘。"""
        if not self._input_enabled:
            self.commit_command_submission(command)
            return

        self._entries.append(
            {
                "timestamp": datetime.now(),
                "text": command or "",
                "color_role": "status_info",
                "kind": "command",
            }
        )
        self._trim_entries()

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        command_fmt = QTextCharFormat()
        command_fmt.setForeground(QColor(t("status_info")))
        cursor.insertText(command or "", command_fmt)
        cursor.insertBlock()

        self._input_prompt_start = cursor.position()
        self._render_input_prompt(cursor, "")
        self.setTextCursor(cursor)
        self.scroll_to_prompt()

    def update_progress(self, progress_id: str, message: str):
        progress_id = (progress_id or "").strip()
        if not progress_id or message is None:
            return

        for entry in self._entries:
            if entry.get("kind") == "progress" and entry.get("progress_id") == progress_id:
                entry["timestamp"] = datetime.now()
                entry["text"] = str(message)
                self._rebuild_document_with_scroll_restore()
                self.scroll_to_prompt()
                return

        self._entries.append(
            {
                "timestamp": datetime.now(),
                "text": str(message),
                "kind": "progress",
                "progress_id": progress_id,
            }
        )
        self._trim_entries()
        self._rebuild_document_with_scroll_restore()
        self.scroll_to_prompt()

    def refresh_content_style(self):
        if self._entries or self._input_enabled:
            self._rebuild_document()

    def current_input(self) -> str:
        plain_text = self.toPlainText()
        if self._input_start > len(plain_text):
            self._input_start = len(plain_text)
        return plain_text[self._input_start:]

    def set_current_input(self, text: str):
        self._replace_current_input(text)
        self._move_cursor_to_end()
        self.input_text_changed.emit(self.current_input())

    def clear_current_input(self):
        self._replace_current_input("")
        self._move_cursor_to_end()
        self.input_text_changed.emit("")

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy) or event.matches(QKeySequence.SelectAll):
            super().keyPressEvent(event)
            return

        if not self._input_enabled or self._input_locked:
            if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right, Qt.Key_PageUp, Qt.Key_PageDown):
                super().keyPressEvent(event)
            return

        cursor = self.textCursor()
        is_in_input_line = cursor.position() >= self._input_start and cursor.anchor() >= self._input_prompt_start

        if event.key() == Qt.Key_Up and is_in_input_line:
            self.history_prev_requested.emit()
            return

        if event.key() == Qt.Key_Down and is_in_input_line:
            self.history_next_requested.emit()
            return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if cursor.position() < self._input_prompt_start or self._browse_mode:
                self._browse_mode = False
                self._move_cursor_to_end(ensure_visible=True)
                self._show_input_cursor()
                return
            command = self.current_input()
            self._replace_current_input("")
            self.input_text_changed.emit("")
            self.command_submitted.emit(command)
            return

        if event.key() == Qt.Key_Backspace and cursor.position() <= self._input_start:
            return

        if event.key() == Qt.Key_Left and cursor.position() <= self._input_start:
            return

        if event.key() == Qt.Key_Home:
            cursor = self.textCursor()
            cursor.setPosition(self._input_start)
            self.setTextCursor(cursor)
            return

        if event.key() == Qt.Key_Delete and cursor.position() < self._input_start:
            return

        if event.text() or event.key() in (Qt.Key_Backspace, Qt.Key_Delete) or event.matches(QKeySequence.Paste):
            self._protect_cursor()
        super().keyPressEvent(event)
        if event.text() or event.key() in (Qt.Key_Backspace, Qt.Key_Delete) or event.matches(QKeySequence.Paste):
            self.input_text_changed.emit(self.current_input())

    def mousePressEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        self._pressed_in_input_line = cursor.position() >= self._input_prompt_start
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if not self._input_enabled or self._input_locked:
            return
        if self.textCursor().hasSelection():
            self._browse_mode = True
            self._hide_input_cursor()
            return
        if self._pressed_in_input_line or self._is_scrolled_to_bottom():
            self._browse_mode = False
            self._move_cursor_to_end(ensure_visible=False, preserve_scroll=not self._is_scrolled_to_bottom())
            self._show_input_cursor()
            return

        self._browse_mode = True
        self._move_cursor_to_end(ensure_visible=False, preserve_scroll=True)
        self._hide_input_cursor()

    def focusInEvent(self, event):
        super().focusInEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t('bg_mid')};
                color: {t('text_primary')};
                border: 1px solid {t('border')};
                padding: 2px;
            }}
            QMenu::item {{
                padding: 6px 18px 6px 8px;
                margin: 1px 2px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {t('selection_bg')};
                color: {t('text_primary')};
            }}
        """)
        clear_action = menu.addAction("清空窗口内容")
        clear_action.setEnabled(bool(self._entries))
        selected_action = menu.exec_(self.viewport().mapToGlobal(pos))
        if selected_action == clear_action:
            self.clear_requested.emit()

    def _rebuild_document(self):
        current_input = self.current_input() if self._input_enabled else ""

        self.clear()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Start)

        for entry in self._entries:
            self._render_entry(cursor, entry)

        self._input_prompt_start = cursor.position()
        if self._input_enabled:
            self._render_input_prompt(cursor, current_input)
        else:
            self._input_start = self._input_prompt_start

        self.setTextCursor(cursor)
        if self._input_enabled and not self._browse_mode and not self._input_locked:
            self._show_input_cursor()
            self.ensureCursorVisible()
        else:
            self._hide_input_cursor()

    def _rebuild_document_with_scroll_restore(self):
        scroll_bar = self.verticalScrollBar()
        h_scroll_bar = self.horizontalScrollBar()
        was_at_bottom = self._is_scrolled_to_bottom()
        v_value = scroll_bar.value()
        h_value = h_scroll_bar.value()
        self._rebuild_document()
        if was_at_bottom:
            scroll_bar.setValue(scroll_bar.maximum())
        else:
            scroll_bar.setValue(min(v_value, scroll_bar.maximum()))
            h_scroll_bar.setValue(min(h_value, h_scroll_bar.maximum()))

    def _render_entry(self, cursor: QTextCursor, entry: dict):
        timestamp_fmt = QTextCharFormat()
        timestamp_fmt.setForeground(QColor(t("text_hint")))

        content_fmt = QTextCharFormat()
        content_fmt.setForeground(QColor(self._resolve_entry_color(entry)))

        if self._show_timestamps:
            cursor.insertText(f"{self._format_timestamp(entry.get('timestamp'))} ", timestamp_fmt)
        if entry.get("kind") == "command":
            prompt_fmt = QTextCharFormat()
            prompt_fmt.setForeground(QColor("#39b54a"))
            cursor.insertText(self._prompt_text, prompt_fmt)
        elif entry.get("label"):
            label_fmt = QTextCharFormat()
            label_fmt.setForeground(QColor(entry.get("color") or t("text_primary")))
            cursor.insertText(entry["label"], label_fmt)
        cursor.insertText(entry.get("text", ""), content_fmt)
        cursor.insertBlock()

    def _render_input_prompt(self, cursor: QTextCursor, current_input: str):
        if self._show_timestamps:
            timestamp_fmt = QTextCharFormat()
            timestamp_fmt.setForeground(QColor(t("text_hint")))
            cursor.insertText(f"{self._format_timestamp(self._input_line_timestamp())} ", timestamp_fmt)

        prompt_fmt = QTextCharFormat()
        prompt_fmt.setForeground(QColor("#39b54a"))

        input_fmt = QTextCharFormat()
        input_fmt.setForeground(QColor("#39b54a"))

        cursor.insertText(self._prompt_text, prompt_fmt)
        self._input_start = cursor.position()
        if current_input:
            cursor.insertText(current_input, input_fmt)

    def _trim_entries(self):
        overflow = len(self._entries) - self.MAX_ENTRIES
        if overflow > 0:
            del self._entries[:overflow]

    def append_stream_log_batch(self, message: str):
        if not message:
            return
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()
        should_follow = self._is_scrolled_to_bottom() and not self._browse_mode
        current_input = self.current_input() if self._input_enabled else ""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        if self._input_enabled:
            cursor.setPosition(self._input_prompt_start)
            cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()

        timestamp_fmt = QTextCharFormat()
        timestamp_fmt.setForeground(QColor(t("text_hint")))
        content_fmt = QTextCharFormat()
        content_fmt.setForeground(QColor(t("text_primary")))

        for line in (message or "").splitlines() or [""]:
            if self._show_timestamps:
                cursor.insertText(f"{self._format_timestamp(datetime.now())} ", timestamp_fmt)
            cursor.insertText(line, content_fmt)
            cursor.insertBlock()

        self._trim_stream_blocks()
        self._input_prompt_start = cursor.position()
        if self._input_enabled:
            self._render_input_prompt(cursor, current_input)
        else:
            self._input_start = self._input_prompt_start

        self.setTextCursor(cursor)
        if should_follow:
            self.scroll_to_prompt()
        else:
            self.verticalScrollBar().setValue(v_scroll)
            self.horizontalScrollBar().setValue(h_scroll)

    def _trim_stream_blocks(self):
        doc = self.document()
        excess = doc.blockCount() - self.MAX_STREAM_LOG_BLOCKS
        if excess <= 0:
            return
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        for _ in range(excess):
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _replace_current_input(self, text: str):
        cursor = self.textCursor()
        cursor.setPosition(self._input_start)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def _move_cursor_to_end(self, ensure_visible: bool = False, preserve_scroll: bool = False):
        v_scroll = self.verticalScrollBar().value()
        h_scroll = self.horizontalScrollBar().value()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        if cursor.position() < self._input_start:
            cursor.setPosition(self._input_start)
        self.setTextCursor(cursor)
        if preserve_scroll:
            self.verticalScrollBar().setValue(v_scroll)
            self.horizontalScrollBar().setValue(h_scroll)
        elif ensure_visible:
            self.ensureCursorVisible()

    def scroll_to_prompt(self):
        self._browse_mode = False
        self._move_cursor_to_end(ensure_visible=True)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def _protect_cursor(self, force_end: bool = False):
        cursor = self.textCursor()
        if force_end or cursor.position() < self._input_start or cursor.anchor() < self._input_prompt_start:
            self._browse_mode = False
            self._move_cursor_to_end(ensure_visible=True)
            self._show_input_cursor()

    def _auto_copy_selection(self, available: bool):
        if available:
            self.copy()

    def _show_input_cursor(self):
        if self.textCursor().hasSelection():
            self.setCursorWidth(0)
            return
        self.setCursorWidth(self._visible_cursor_width if self._input_enabled and not self._input_locked else 0)

    def _hide_input_cursor(self):
        self.setCursorWidth(0)

    def _on_selection_changed(self):
        if self.textCursor().hasSelection():
            self._hide_input_cursor()
        elif self._browse_mode:
            self._hide_input_cursor()
        else:
            self._show_input_cursor()

    def _input_line_timestamp(self) -> datetime:
        if self._entries:
            return self._entries[-1].get("timestamp") or datetime.now()
        return datetime.now()

    def _is_scrolled_to_bottom(self) -> bool:
        scroll_bar = self.verticalScrollBar()
        return scroll_bar.value() >= scroll_bar.maximum()

    @staticmethod
    def _infer_color_role(color: str):
        if not color:
            return None
        for role in ("status_offline", "status_info", "text_primary", "text_hint"):
            if color == t(role):
                return role
        return None

    @staticmethod
    def _resolve_entry_color(entry: dict):
        color_role = entry.get("color_role")
        if color_role:
            return t(color_role)
        return entry.get("color") or t("text_primary")

    @staticmethod
    def _format_timestamp(timestamp: datetime) -> str:
        if not timestamp:
            timestamp = datetime.now()
        return timestamp.strftime("%m-%d %H:%M:%S")


class ShortcutEditDialog(AdaptiveDialog):
    """快捷命令编辑对话框。"""

    def __init__(self, command: str, parent=None):
        super().__init__(parent)
        self.command_input = None
        self._build_ui(command)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)

    def _build_ui(self, command: str):
        self.setWindowTitle("编辑快捷方式")
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)

        layout = self.init_dialog_layout(
            (280, 140),
            min_size=(260, 140),
            layout_margins=(16, 14, 16, 14),
            spacing=12,
            max_width_ratio=0.55,
            max_height_ratio=0.45,
        )

        label = QLabel("命令:")
        label.setStyleSheet(f"color: {t('text_primary')};")
        layout.addWidget(label)

        self.command_input = QLineEdit()
        self.command_input.setText(command)
        self.command_input.setClearButtonEnabled(False)
        self.command_input.setStyleSheet(self._get_input_stylesheet())
        self.command_input.returnPressed.connect(self.accept)
        layout.addWidget(self.command_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        confirm_btn = QPushButton()
        confirm_btn.setIcon(QIcon(":/icons/common/ok.png"))
        confirm_btn.setIconSize(QSize(18, 18))
        confirm_btn.setToolTip("确认")
        confirm_btn.setFixedSize(60, 32)
        confirm_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        confirm_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton()
        cancel_btn.setIcon(QIcon(":/icons/common/cancel.png"))
        cancel_btn.setIconSize(QSize(18, 18))
        cancel_btn.setToolTip("取消")
        cancel_btn.setFixedSize(60, 32)
        cancel_btn.setStyleSheet(StyleManager.get_ACTION_BUTTON())
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(confirm_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def command_text(self) -> str:
        return self.command_input.text().strip()

    @staticmethod
    def _get_input_stylesheet():
        return f"""
        QLineEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 5px 6px;
            selection-background-color: {t('selection_bg')};
        }}
        QLineEdit:focus {{
            border: 1px solid {t('border_hover')};
        }}
        """


@register_page("调试", order=2, icon=":/icons/system/console.png")
class DebugPage(BasePage):
    """设备调试页面"""

    MAX_SHORTCUTS = 50
    MAX_HISTORY = 100
    PENDING_RECONNECT_DELAY_MS = 800
    DEFAULT_SHORTCUT_COMMANDS = [
        'startlogp2p 31',
        'startlogp2p 0',
        'ls /mnt/nand/',
        'echo "70 27" > /tmp/battery_power',
    ]
    SHORTCUT_EXPANDED_HEIGHT = 96
    SHORTCUT_CHIP_HEIGHT = 24
    SHORTCUT_MIN_BUTTON_WIDTH = 78
    COMMAND_TYPES = [("syscmd", "syscmd")]
    SUPPRESSED_CONNECT_MESSAGES = {
        "正在查询设备密码...",
        "正在连接设备...",
    }
    SUPPRESSED_CONNECT_PREFIXES = (
        "已识别为非SIOT设备，使用P2P协议连接",
        "检测到SIOT设备，使用TPSRTC协议连接",
        "检测到非SIOT设备，使用P2P协议连接",
        "检测到非SIOT设备，正在使用P2P协议连接",
        "P2P登录请求已发送，正在等待设备响应",
        "P2P服务器登录成功，正在建立设备通道",
        "P2P设备连接成功，正在初始化交互",
    )

    request_connect = pyqtSignal(str, str, str, str, str, str)
    request_command = pyqtSignal(str, int, str)
    request_disconnect = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.page_name = "调试"
        self.default_timeout_ms = DEFAULT_COMMAND_TIMEOUT_MS
        self.connected = False
        self.connecting = False
        self.canceling_connect = False
        self.command_running = False
        self._executing_command = ""
        self.current_context = {}
        self.shortcut_commands = []
        self.shortcut_collapsed = False
        self.command_history = []
        self.history_index = None
        self.history_draft = ""
        self._active_suggestion_context = None
        self._history_suggestion_suppressed_contexts = set()
        self._history_programmatic_update_contexts = set()
        self.command_type_prefix = self.COMMAND_TYPES[0][1]
        self.last_command_source = "input"
        self.download_root = self._default_download_root()
        self.pending_target_sn = ""
        self._timestamp_on_icon = QIcon(":/icons/common/timestamp.png")
        self._timestamp_off_icon = self._create_gray_icon(":/icons/common/timestamp.png")
        self._console_suppress_until = 0.0
        self._pending_output_entries = []
        self._pending_stream_log_entries = []
        self._stream_log_active = False
        self._pending_stream_log_state = None
        self._last_command_failed = False
        self.history_popup = None
        self._output_flush_timer = QTimer(self)
        self._output_flush_timer.setInterval(120)
        self._output_flush_timer.timeout.connect(self._flush_pending_output)
        self._stream_log_flush_timer = QTimer(self)
        self._stream_log_flush_timer.setInterval(180)
        self._stream_log_flush_timer.timeout.connect(self._flush_pending_stream_logs)

        self.init_ui()
        self.init_worker()

    def init_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(5, 5, 5, 5)
        page_layout.setSpacing(2)

        self.connect_group = QGroupBox("连接")
        self.connect_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        connect_layout = QVBoxLayout(self.connect_group)
        connect_layout.setContentsMargins(8, 8, 4, 4)
        connect_layout.setSpacing(4)

        connect_frame = QFrame()
        self._apply_plain_toolbar_style(connect_frame)
        self._connect_frame = connect_frame
        connect_frame.setFixedHeight(34)
        connect_frame_layout = QHBoxLayout(connect_frame)
        connect_frame_layout.setContentsMargins(2, 2, 2, 2)
        connect_frame_layout.setSpacing(8)

        login_panel = QFrame()
        login_panel.setFrameShape(QFrame.NoFrame)
        login_panel_layout = QHBoxLayout(login_panel)
        login_panel_layout.setContentsMargins(0, 0, 0, 0)
        login_panel_layout.setSpacing(10)

        sn_label = QLabel("设备SN:")
        sn_label.setFixedWidth(52)

        self.sn_input = QLineEdit()
        self.sn_input.setPlaceholderText("支持SIOT和非SIOT设备")
        self.sn_input.returnPressed.connect(self.on_connect_button_clicked)
        self.sn_input.textChanged.connect(self.on_sn_input_changed)

        self.connect_btn = QPushButton()
        self.connect_btn.clicked.connect(self.on_connect_button_clicked)
        self.connect_btn.setFixedSize(72, 28)
        self.connect_btn.setIconSize(QSize(16, 16))

        login_panel_layout.addWidget(sn_label)
        login_panel_layout.addWidget(self.sn_input, 1)
        login_panel_layout.addWidget(self.connect_btn)

        download_panel = QFrame()
        download_panel.setFrameShape(QFrame.NoFrame)
        download_panel_layout = QHBoxLayout(download_panel)
        download_panel_layout.setContentsMargins(0, 0, 0, 0)
        download_panel_layout.setSpacing(10)

        download_label = QLabel("下载位置:")
        download_label.setFixedWidth(64)

        self.download_path_label = PathDisplayLabel()
        self.download_path_label.setMinimumHeight(28)
        self.download_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.download_path_label.setToolTip("双击打开目录")
        self.download_path_label.double_clicked.connect(self.open_download_directory)
        self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())

        self.choose_download_path_btn = QPushButton()
        self.choose_download_path_btn.setFixedSize(32, 28)
        self.choose_download_path_btn.setIcon(QIcon(":/icons/common/dir.png"))
        self.choose_download_path_btn.setIconSize(QSize(16, 16))
        self.choose_download_path_btn.setToolTip("选择下载目录")
        self.choose_download_path_btn.clicked.connect(self.choose_download_directory)

        download_panel_layout.addWidget(download_label)
        download_panel_layout.addWidget(self.download_path_label, 1)
        download_panel_layout.addWidget(self.choose_download_path_btn)

        connect_frame_layout.addWidget(login_panel, 1)
        connect_frame_layout.addWidget(download_panel, 1)
        connect_layout.addWidget(connect_frame)

        self.command_group = QGroupBox()
        self.command_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        command_layout = QVBoxLayout(self.command_group)
        command_layout.setContentsMargins(8, 6, 8, 8)
        command_layout.setSpacing(4)

        command_header = QHBoxLayout()
        command_header.setContentsMargins(0, 0, 0, 0)
        command_header.setSpacing(8)

        command_title_label = QLabel("交互")
        command_title_label.setStyleSheet(f"color: {t('text_primary')}; font-weight: 600;")

        command_hint_label = QLabel("（交互卡顿时右键清空一下窗口）")
        command_hint_label.setStyleSheet(f"color: {t('text_hint')};")

        command_header.addWidget(command_title_label)
        command_header.addWidget(command_hint_label)
        command_header.addStretch(1)
        command_layout.addLayout(command_header)

        self.console_edit = DebugConsoleEdit()
        self.console_edit.setStyleSheet(self._get_console_stylesheet())
        self.console_edit.set_input_enabled(False)
        self.console_edit.command_submitted.connect(self.on_console_command_submitted)
        self.console_edit.history_prev_requested.connect(self.on_history_prev_requested_from_console)
        self.console_edit.history_next_requested.connect(self.on_history_next_requested_from_console)
        self.console_edit.clear_requested.connect(self.on_console_clear_requested)
        self.console_edit.input_text_changed.connect(self.on_console_input_text_changed)
        self.console_edit.installEventFilter(self)
        command_layout.addWidget(self.console_edit, 1)

        command_input_frame = QFrame()
        self._apply_plain_toolbar_style(command_input_frame)
        self._command_input_frame = command_input_frame
        command_input_frame.setFixedHeight(34)
        command_input_layout = QHBoxLayout(command_input_frame)
        command_input_layout.setContentsMargins(2, 2, 2, 2)
        command_input_layout.setSpacing(8)

        self.show_timestamp_checkbox = QPushButton()
        self.show_timestamp_checkbox.setCheckable(True)
        self.show_timestamp_checkbox.setChecked(True)
        self.show_timestamp_checkbox.setFixedSize(32, 28)
        self.show_timestamp_checkbox.setIconSize(QSize(18, 18))
        self.show_timestamp_checkbox.setToolTip("显示/隐藏时间戳")
        self.show_timestamp_checkbox.toggled.connect(self.on_show_timestamp_toggled)
        self._update_timestamp_toggle_icon(True)

        self.command_type_combo = NoWheelComboBox()
        self.command_type_combo.setFixedSize(92, 28)
        self.command_type_combo.setStyleSheet(StyleManager.get_COMBOBOX())
        for text, prefix in self.COMMAND_TYPES:
            self.command_type_combo.addItem(text, prefix)
        self.command_type_combo.currentIndexChanged.connect(self.on_command_type_changed)

        self.command_input = HistoryLineEdit()
        self.command_input.setPlaceholderText("直接输入命令内容，回车发送...")
        self.command_input.setClearButtonEnabled(True)
        self.command_input.returnPressed.connect(self.on_send_button_clicked)
        self.command_input.history_prev_requested.connect(self.on_history_prev_requested_from_input)
        self.command_input.history_next_requested.connect(self.on_history_next_requested_from_input)
        self.command_input.textChanged.connect(self.on_command_input_text_changed)
        self.command_input.installEventFilter(self)

        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(84, 28)
        self.send_btn.setIcon(QIcon(":/icons/common/send.png"))
        self.send_btn.setIconSize(QSize(16, 16))
        self.send_btn.setToolTip("发送命令")
        self.send_btn.clicked.connect(self.on_send_button_clicked)

        self.add_shortcut_btn = QPushButton()
        self.add_shortcut_btn.setFixedSize(28, 28)
        self.add_shortcut_btn.setIcon(QIcon(":/icons/common/add.png"))
        self.add_shortcut_btn.setIconSize(QSize(16, 16))
        self.add_shortcut_btn.setToolTip("添加到快捷方式")
        self.add_shortcut_btn.clicked.connect(self.on_add_shortcut_clicked)

        self.toggle_shortcut_btn = QPushButton()
        self.toggle_shortcut_btn.setFixedSize(28, 28)
        self.toggle_shortcut_btn.setIcon(QIcon(":/icons/common/expand.png"))
        self.toggle_shortcut_btn.setIconSize(QSize(16, 16))
        self.toggle_shortcut_btn.setToolTip("收起快捷方式")
        self.toggle_shortcut_btn.clicked.connect(self.on_toggle_shortcuts_clicked)

        command_input_layout.addWidget(self.show_timestamp_checkbox)
        command_input_layout.addWidget(self.command_type_combo)
        command_input_layout.addWidget(self.command_input, 1)
        command_input_layout.addWidget(self.send_btn)
        command_input_layout.addWidget(self.add_shortcut_btn)
        command_input_layout.addWidget(self.toggle_shortcut_btn)
        command_layout.addWidget(command_input_frame, 0)

        self.shortcut_frame = QFrame()
        self.shortcut_frame.setFrameShape(QFrame.StyledPanel)
        self.shortcut_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())
        self._shortcut_frame = self.shortcut_frame
        self.shortcut_frame.setFixedHeight(self.SHORTCUT_EXPANDED_HEIGHT)
        shortcut_layout = QVBoxLayout(self.shortcut_frame)
        shortcut_layout.setContentsMargins(4, 4, 4, 4)
        shortcut_layout.setSpacing(4)

        self.shortcut_scroll = QScrollArea()
        self.shortcut_scroll.setWidgetResizable(False)
        self.shortcut_scroll.setFrameShape(QFrame.NoFrame)
        self.shortcut_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.shortcut_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.shortcut_scroll.setStyleSheet(StyleManager.get_SCROLL_AREA())
        self.shortcut_scroll.setContextMenuPolicy(Qt.CustomContextMenu)
        self.shortcut_scroll.customContextMenuRequested.connect(self.on_shortcut_scroll_context_menu)
        self.shortcut_scroll.viewport().setContextMenuPolicy(Qt.CustomContextMenu)
        self.shortcut_scroll.viewport().customContextMenuRequested.connect(self.on_shortcut_scroll_context_menu)

        self.shortcut_hint_label = QLabel(
            "长按快捷按钮拖动排序，右键按钮编辑/删除，右键空白区恢复默认/清空",
            self.shortcut_scroll.viewport(),
        )
        self.shortcut_hint_label.setObjectName("shortcutHintLabel")
        self.shortcut_hint_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.shortcut_hint_label.setStyleSheet(self._get_shortcut_hint_stylesheet())

        self.shortcut_container = QWidget()
        self.shortcut_flow_layout = FlowLayout(self.shortcut_container, margin=0, h_spacing=4, v_spacing=4)
        self.shortcut_container.setLayout(self.shortcut_flow_layout)
        self.shortcut_container.setContextMenuPolicy(Qt.CustomContextMenu)
        self.shortcut_container.customContextMenuRequested.connect(self.on_shortcut_blank_context_menu)

        self.shortcut_scroll.setWidget(self.shortcut_container)
        self.shortcut_hint_label.lower()
        shortcut_layout.addWidget(self.shortcut_scroll)
        command_layout.addWidget(self.shortcut_frame, 0)

        page_layout.addWidget(self.connect_group, 0)
        page_layout.addWidget(self.command_group, 1)

        self.history_popup = HistorySuggestionPopup(self)
        self.history_popup.command_clicked.connect(self.on_history_popup_command_clicked)
        self.history_popup.delete_requested.connect(self.on_history_popup_delete_requested)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.on_command_type_changed()
        self.update_send_button()
        self._hide_history_suggestions()
        self.update_connect_button()

    def _apply_plain_toolbar_style(self, frame):
        """工具条容器不显示外层边框。"""
        frame.setFrameShape(QFrame.NoFrame)
        frame.setFrameShadow(QFrame.Plain)
        frame.setStyleSheet("QFrame { border: none; background: transparent; }")

    @staticmethod
    def _get_compact_group_box_stylesheet():
        return f"""
        QGroupBox {{
            color: {t('text_primary')};
            font-size: 12px;
            font-weight: bold;
            border: 1px solid {t('border')};
            border-radius: 4px;
            margin-top: 6px;
            margin-bottom: 4px;
            padding-top: 4px;
            background-color: transparent;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }}
        """

    def init_worker(self):
        self.worker_thread = QThread(self)
        self.worker = SiotDebugWorker()
        self.worker.moveToThread(self.worker_thread)

        self.request_connect.connect(self.worker.connect_with_accounts)
        self.request_command.connect(self.worker.execute_command)
        self.request_disconnect.connect(self.worker.disconnect_device)

        self.worker.status_message.connect(self.on_worker_status_message)
        self.worker.connected.connect(self.on_connected)
        self.worker.connect_failed.connect(self.on_connect_failed)
        self.worker.disconnected.connect(self.on_disconnected)
        self.worker.command_output.connect(self.append_output)
        self.worker.stream_log_output.connect(self.append_stream_log_output)
        self.worker.command_progress.connect(self.on_command_progress)
        self.worker.command_failed.connect(self.on_command_failed)
        self.worker.command_finished.connect(self.on_command_finished)

        self.worker_thread.start()

    def eventFilter(self, watched, event):
        if self.history_popup is not None and self.history_popup.isVisible():
            if event.type() == QEvent.MouseButtonPress:
                if self._should_hide_history_popup_on_click(watched, event):
                    self._hide_history_suggestions()

        if event.type() == QEvent.KeyPress:
            if watched is self.command_input:
                if self._handle_history_popup_key_event("input", self.command_input.text(), event):
                    return True
            elif watched is self.console_edit:
                if self._handle_history_popup_key_event("console", self.console_edit.current_input(), event):
                    return True
        return super().eventFilter(watched, event)

    def on_page_show(self):
        self.show_info("调试页面")
        self.refresh_shortcut_area_geometry()

    def load_config(self):
        app_config = config_manager.load_app_config()
        self.sn_input.setText((app_config.last_debug_sn or "").strip())
        self.download_root = self._normalize_download_root(app_config.debug_download_path)
        self.update_download_path_label()
        if not app_config.debug_shortcuts_initialized:
            if app_config.debug_shortcuts:
                app_config.debug_shortcuts_initialized = True
            else:
                app_config.debug_shortcuts = list(self.DEFAULT_SHORTCUT_COMMANDS)
                app_config.debug_shortcuts_initialized = True
            config_manager.save_app_config(app_config)
        self.shortcut_commands = [
            normalized
            for cmd in app_config.debug_shortcuts[:self.MAX_SHORTCUTS]
            if cmd.strip()
            for normalized in [self._normalize_display_command(cmd)]
            if normalized
        ]
        self.command_history = [
            normalized
            for cmd in app_config.debug_command_history[:self.MAX_HISTORY]
            if cmd.strip()
            for normalized in [self._normalize_history_command(cmd)]
            if normalized
        ]
        self.history_index = None
        self.history_draft = ""
        self.refresh_shortcut_buttons()

    def save_config(self):
        app_config = config_manager.load_app_config()
        app_config.last_debug_sn = self.sn_input.text().strip()
        app_config.debug_download_path = self.download_root
        app_config.debug_shortcuts = self.shortcut_commands[:self.MAX_SHORTCUTS]
        app_config.debug_shortcuts_initialized = True
        app_config.debug_command_history = self.command_history[-self.MAX_HISTORY:]
        config_manager.save_app_config(app_config)

    def _normalize_history_command(self, command):
        return self._normalize_display_command(command)

    def _persist_command_history(self):
        self.save_config()

    def _record_successful_command(self, command):
        command = self._normalize_history_command(command)
        if not command:
            return

        if command in self.command_history:
            self.command_history.remove(command)
        self.command_history.append(command)
        if len(self.command_history) > self.MAX_HISTORY:
            self.command_history = self.command_history[-self.MAX_HISTORY:]
        self.history_index = None
        self.history_draft = ""
        self._persist_command_history()

    def on_sn_input_changed(self, _text):
        self.save_config()

    def connect_to_device_sn(self, sn: str):
        sn = (sn or "").strip()
        if not sn:
            self.show_warning("设备SN为空，无法连接")
            return

        self.pending_target_sn = sn
        self.sn_input.setText(sn)

        if self.connecting and not self.connected:
            self.on_cancel_connect_clicked()
            return

        if self.connected:
            current_sn = str(self.current_context.get("sn") or self.sn_input.text() or "").strip()
            if current_sn == sn:
                self.pending_target_sn = ""
                self.show_info(f"设备 {sn} 已连接")
                return
            self.on_disconnect_clicked()
            return

        self._start_pending_connect()

    def _start_pending_connect(self):
        target_sn = (self.pending_target_sn or "").strip()
        if not target_sn or self.connected or self.connecting:
            return

        self.sn_input.setText(target_sn)
        self.pending_target_sn = ""
        self.on_connect_button_clicked()

    def _schedule_pending_connect(self):
        if not (self.pending_target_sn or "").strip():
            return
        QTimer.singleShot(self.PENDING_RECONNECT_DELAY_MS, self._start_pending_connect)

    def on_connect_button_clicked(self):
        if self.connecting and not self.connected:
            self.on_cancel_connect_clicked()
            return

        if self.connected:
            self.on_disconnect_clicked()
            return

        seetong_username, seetong_password = get_seetong_account_config()
        seetong_username = (seetong_username or "").strip()
        seetong_password = (seetong_password or "").strip()
        if not seetong_username or not seetong_password:
            prompt_configure_account(self, account_type="seetong")
            return

        sn = self.sn_input.text().strip()
        if not sn:
            self.show_warning("请输入设备SN")
            return

        env, device_username, device_password = get_account_config()
        if not device_username or not device_password:
            prompt_configure_account(self, account_type="device")
            return

        self.set_connecting_state(True)
        self.request_connect.emit(
            sn,
            env,
            device_username,
            device_password,
            seetong_username,
            seetong_password,
        )

    def choose_download_directory(self):
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "选择文件下载目录",
            self.download_root,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not selected_dir:
            return
        self.download_root = self._normalize_download_root(selected_dir)
        self.update_download_path_label()
        self.save_config()

    def open_download_directory(self):
        directory = Path(self.download_root)
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def update_download_path_label(self):
        self.download_path_label.setText(self.download_root)
        self.download_path_label.setToolTip(f"{self.download_root}\n双击打开目录")

    def _update_timestamp_toggle_icon(self, checked: bool):
        self.show_timestamp_checkbox.setIcon(self._timestamp_on_icon if checked else self._timestamp_off_icon)

    @staticmethod
    def _create_gray_icon(resource_path: str) -> QIcon:
        pixmap = QPixmap(resource_path)
        if pixmap.isNull():
            return QIcon()

        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                alpha = color.alpha()
                gray = int(color.red() * 0.299 + color.green() * 0.587 + color.blue() * 0.114)
                color.setRgb(gray, gray, gray, alpha)
                image.setPixelColor(x, y, color)
        return QIcon(QPixmap.fromImage(image))

    def on_cancel_connect_clicked(self):
        if not self.connecting or self.connected or self.canceling_connect:
            return

        self.canceling_connect = True
        self.update_connect_button()
        self.worker.cancel_pending_connect()
        self.connecting = False
        self.canceling_connect = False
        self.current_context = {}
        self.sn_input.setEnabled(True)
        self.console_edit.set_input_enabled(False)
        self.console_edit.set_input_locked(False)
        self.command_input.setEnabled(True)
        self.command_type_combo.setEnabled(True)
        self.update_shortcut_controls()
        self.update_send_button()
        self.update_connect_button()
        self.append_output("已取消连接")
        self.show_info("已取消连接")
        self._schedule_pending_connect()

    def on_disconnect_clicked(self):
        if not self.connected:
            return

        self.connecting = True
        self.console_edit.set_input_enabled(False)
        self.console_edit.set_input_locked(True)
        self.update_connect_button()
        self.append_output("正在断开连接...")
        self.request_disconnect.emit()

    def on_console_command_submitted(self, command):
        self._submit_command(command, source="console")

    def on_send_button_clicked(self):
        command = self._normalize_display_command(self.command_input.text())
        if not command:
            return
        self._submit_command(command, source="input")

    def on_add_shortcut_clicked(self):
        command = self._normalize_display_command(self.command_input.text())
        if not command:
            self.show_warning("请输入命令后再添加快捷方式")
            return

        if len(self.shortcut_commands) >= self.MAX_SHORTCUTS and command not in self.shortcut_commands:
            self.show_warning(f"最多只能添加 {self.MAX_SHORTCUTS} 个快捷方式")
            return

        if command in self.shortcut_commands:
            self.shortcut_commands.remove(command)

        self.shortcut_commands.append(command)
        self.shortcut_commands = self.shortcut_commands[:self.MAX_SHORTCUTS]
        self.refresh_shortcut_buttons()
        self.save_config()
        self.show_success("快捷方式已添加", 1500)

    def on_toggle_shortcuts_clicked(self):
        self.shortcut_collapsed = not self.shortcut_collapsed
        self.shortcut_frame.setVisible(not self.shortcut_collapsed)
        self.toggle_shortcut_btn.setToolTip("展开快捷方式" if self.shortcut_collapsed else "收起快捷方式")
        if not self.shortcut_collapsed:
            self.refresh_shortcut_area_geometry()

    def on_show_timestamp_toggled(self, checked):
        self._update_timestamp_toggle_icon(checked)
        self.console_edit.set_show_timestamps(checked)

    def on_command_type_changed(self):
        self.command_type_prefix = self.current_command_prefix()
        self.console_edit.setPlaceholderText(
            f"登录后可直接输入命令，回车发送指令..."
        )

    def on_shortcut_clicked(self, command):
        self.command_input.setText(command)
        self._submit_command(command, source="shortcut")

    def on_delete_shortcut_clicked(self, command):
        if command not in self.shortcut_commands:
            return
        self.shortcut_commands.remove(command)
        self.refresh_shortcut_buttons()
        self.save_config()

    def on_clear_shortcuts_clicked(self):
        if not self.shortcut_commands:
            return
        self.shortcut_commands = []
        self.refresh_shortcut_buttons()
        self.save_config()
        self.show_success("快捷方式已清空", 1500)

    def on_restore_default_shortcuts_clicked(self):
        self.shortcut_commands = list(self.DEFAULT_SHORTCUT_COMMANDS[:self.MAX_SHORTCUTS])
        self.refresh_shortcut_buttons()
        self.save_config()
        self.show_success("已恢复默认快捷方式", 1500)

    def on_shortcut_reorder_requested(self, dragged_command, target_command):
        if dragged_command not in self.shortcut_commands or target_command not in self.shortcut_commands:
            return
        if dragged_command == target_command:
            return

        dragged_index = self.shortcut_commands.index(dragged_command)
        target_index = self.shortcut_commands.index(target_command)
        command = self.shortcut_commands.pop(dragged_index)

        if dragged_index < target_index:
            target_index -= 1

        self.shortcut_commands.insert(target_index, command)
        self.refresh_shortcut_buttons()
        self.save_config()

    def on_edit_shortcut_clicked(self, command):
        if command not in self.shortcut_commands:
            return

        dialog = ShortcutEditDialog(command, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        new_command = dialog.command_text()
        new_command = self._normalize_display_command(new_command)
        if not new_command:
            self.show_warning("快捷命令不能为空")
            return

        if new_command == command:
            return

        if new_command in self.shortcut_commands:
            self.show_warning("该快捷命令已存在")
            return

        index = self.shortcut_commands.index(command)
        self.shortcut_commands[index] = new_command
        self.refresh_shortcut_buttons()
        self.save_config()
        self.show_success("快捷方式已更新", 1500)

    def show_shortcut_context_menu(self, button, pos, command):
        menu = QMenu(button)
        menu.setStyleSheet(self._get_shortcut_context_menu_stylesheet())
        edit_action = menu.addAction("编辑")
        delete_action = menu.addAction("删除")
        menu.ensurePolished()
        menu.adjustSize()
        selected_action = menu.exec_(button.mapToGlobal(pos))

        if selected_action == edit_action:
            self.on_edit_shortcut_clicked(command)
        elif selected_action == delete_action:
            self.on_delete_shortcut_clicked(command)

    def on_shortcut_blank_context_menu(self, pos):
        child = self.shortcut_container.childAt(pos)
        if isinstance(child, QPushButton):
            return

        self._show_shortcut_blank_context_menu(self.shortcut_container.mapToGlobal(pos))

    def on_shortcut_scroll_context_menu(self, pos):
        viewport = self.shortcut_scroll.viewport()
        global_pos = viewport.mapToGlobal(pos)
        container_pos = self.shortcut_container.mapFromGlobal(global_pos)
        child = self.shortcut_container.childAt(container_pos)
        if isinstance(child, QPushButton):
            return

        self._show_shortcut_blank_context_menu(global_pos)

    def _show_shortcut_blank_context_menu(self, global_pos):
        menu = QMenu(self.shortcut_container)
        menu.setStyleSheet(self._get_shortcut_context_menu_stylesheet())
        restore_action = menu.addAction("恢复默认快捷方式")
        clear_action = menu.addAction("清空快捷方式")
        clear_action.setEnabled(bool(self.shortcut_commands))
        selected_action = menu.exec_(global_pos)

        if selected_action == restore_action:
            self.on_restore_default_shortcuts_clicked()
        elif selected_action == clear_action:
            self.on_clear_shortcuts_clicked()

    def on_history_prev_requested_from_input(self):
        current_text = self.command_input.text()
        if self._should_handle_popup_navigation("input", current_text):
            self.history_popup.select_prev()
            return
        value = self._navigate_history(current_text, previous=True)
        if value is not None:
            self._prepare_history_navigation_update("input")
            self.command_input.setText(value)
            self.command_input.setCursorPosition(len(value))

    def on_history_next_requested_from_input(self):
        current_text = self.command_input.text()
        if self._should_handle_popup_navigation("input", current_text):
            self.history_popup.select_next()
            return
        value = self._navigate_history(current_text, previous=False)
        if value is not None:
            self._prepare_history_navigation_update("input")
            self.command_input.setText(value)
            self.command_input.setCursorPosition(len(value))

    def on_history_prev_requested_from_console(self):
        current_text = self.console_edit.current_input()
        if self._should_handle_popup_navigation("console", current_text):
            self.history_popup.select_prev()
            return
        value = self._navigate_history(current_text, previous=True)
        if value is not None:
            self._prepare_history_navigation_update("console")
            self.console_edit.set_current_input(value)

    def on_history_next_requested_from_console(self):
        current_text = self.console_edit.current_input()
        if self._should_handle_popup_navigation("console", current_text):
            self.history_popup.select_next()
            return
        value = self._navigate_history(current_text, previous=False)
        if value is not None:
            self._prepare_history_navigation_update("console")
            self.console_edit.set_current_input(value)

    def on_command_input_text_changed(self, text):
        self._handle_history_input_changed("input", text)

    def on_console_input_text_changed(self, text):
        self._handle_history_input_changed("console", text)

    def on_history_popup_command_clicked(self, command):
        self._apply_history_suggestion(self._active_suggestion_context, command, submit=False)

    def on_history_popup_delete_requested(self, command):
        self._delete_history_suggestion(self._active_suggestion_context, command)

    def _prepare_history_navigation_update(self, context):
        self._history_suggestion_suppressed_contexts.add(context)
        self._history_programmatic_update_contexts.add(context)
        if self._active_suggestion_context == context:
            self._hide_history_suggestions()

    def _handle_history_input_changed(self, context, text):
        if context in self._history_programmatic_update_contexts:
            self._history_programmatic_update_contexts.discard(context)
            return

        if context in self._history_suggestion_suppressed_contexts:
            self._history_suggestion_suppressed_contexts.discard(context)

        self._update_history_suggestions(context, text)

    def _should_handle_popup_navigation(self, context, current_text):
        return (
            bool(str(current_text or "").strip())
            and self._active_suggestion_context == context
            and self.history_popup is not None
            and self.history_popup.isVisible()
            and self.history_popup.has_suggestions()
        )

    def _match_command_history(self, text):
        query = self._normalize_history_command(text)
        if not query:
            return []

        lowered_query = query.lower()
        prefix_matches = []
        for command in reversed(self.command_history):
            lowered_command = command.lower()
            if lowered_command.startswith(lowered_query):
                prefix_matches.append(command)
        return prefix_matches

    def _update_history_suggestions(self, context, text):
        normalized_text = self._normalize_history_command(text)
        if not normalized_text:
            if self._active_suggestion_context == context:
                self._hide_history_suggestions()
            return

        suggestions = self._match_command_history(normalized_text)
        if not suggestions:
            if self._active_suggestion_context == context:
                self._hide_history_suggestions()
            return

        self._active_suggestion_context = context
        self.history_popup.set_suggestions(suggestions)
        self.history_popup.show_popup(
            self._history_popup_position(context),
            self._history_popup_available_width(context),
        )

    def _history_popup_position(self, context):
        if context == "console":
            cursor_rect = self.console_edit.cursorRect()
            popup_origin = cursor_rect.bottomLeft() + QPoint(0, 4)
            return self.console_edit.viewport().mapTo(self, popup_origin)
        return self.command_input.mapTo(self, QPoint(0, self.command_input.height() + 2))

    def _history_popup_available_width(self, context):
        if context == "console":
            viewport_width = self.console_edit.viewport().width()
            cursor_rect = self.console_edit.cursorRect()
            return max(HistorySuggestionPopup.MIN_WIDTH, viewport_width - cursor_rect.x() - 20)
        return self.command_input.width()

    def _hide_history_suggestions(self):
        self._active_suggestion_context = None
        if self.history_popup is not None:
            self.history_popup.hide()

    def _remove_command_history_entry(self, command):
        normalized_command = self._normalize_history_command(command)
        if not normalized_command or normalized_command not in self.command_history:
            return False

        self.command_history = [cmd for cmd in self.command_history if cmd != normalized_command]
        self.history_index = None
        self.history_draft = ""
        self._persist_command_history()
        return True

    def _delete_history_suggestion(self, context, command):
        if not self._remove_command_history_entry(command):
            return

        if not context:
            self._hide_history_suggestions()
            return

        self._update_history_suggestions(context, self._current_history_input(context))

    def _current_history_input(self, context):
        if context == "console":
            return self.console_edit.current_input()
        return self.command_input.text()

    def _apply_history_suggestion(self, context, command, submit=False):
        if not context or not command:
            return

        if context == "console":
            if submit:
                self.console_edit.clear_current_input()
                self._hide_history_suggestions()
                self._submit_command(command, source="console")
                return
            self.console_edit.set_current_input(command)
        else:
            self.command_input.setText(command)
            self.command_input.setCursorPosition(len(command))
            if submit:
                self._hide_history_suggestions()
                self._submit_command(command, source="input")
                return

        self._hide_history_suggestions()

    def _handle_history_popup_key_event(self, context, current_text, event):
        if not self._should_handle_popup_navigation(context, current_text):
            return False
        if context == "console" and self.console_edit.textCursor().position() < self.console_edit._input_start:
            return False

        key = event.key()
        if key == Qt.Key_Up:
            self.history_popup.select_prev()
            return True
        if key == Qt.Key_Down:
            self.history_popup.select_next()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if not self.history_popup.has_active_selection():
                return False
            selected_command = self.history_popup.current_value()
            if selected_command:
                self._apply_history_suggestion(context, selected_command, submit=True)
                return True
            return False
        if key == Qt.Key_Delete:
            if not self.history_popup.has_active_selection():
                return False
            selected_command = self.history_popup.current_value()
            if selected_command:
                self._delete_history_suggestion(context, selected_command)
                return True
            return False
        if key == Qt.Key_Tab:
            selected_command = self.history_popup.current_value()
            if selected_command:
                self._apply_history_suggestion(context, selected_command, submit=False)
            return True
        if key == Qt.Key_Escape:
            self._hide_history_suggestions()
            return True
        return False

    def _should_hide_history_popup_on_click(self, watched, event):
        if self._is_history_popup_widget(watched):
            return False

        if watched in (self.command_input, self.console_edit):
            return False

        widget = watched if isinstance(watched, QWidget) else None
        if self.history_popup is not None and hasattr(event, "globalPos"):
            popup_global_rect = QRect(
                self.history_popup.mapToGlobal(QPoint(0, 0)),
                self.history_popup.size(),
            )
            if popup_global_rect.contains(event.globalPos()):
                return False

        if widget is None or event is None or not hasattr(event, "pos"):
            return True

        global_pos = widget.mapToGlobal(event.pos())
        popup_pos = self.mapFromGlobal(global_pos)
        return not self.history_popup.geometry().contains(popup_pos)

    def _is_history_popup_widget(self, widget):
        current = widget if isinstance(widget, QWidget) else None
        while current is not None:
            if current is self.history_popup:
                return True
            current = current.parentWidget()
        return False

    def _hide_history_suggestions_if_inactive(self):
        if self.history_popup is None or not self.history_popup.isVisible():
            return
        if self.command_input.hasFocus() or self.console_edit.hasFocus():
            return
        self._hide_history_suggestions()

    def _navigate_history(self, current_text, previous=True):
        if not self.command_history:
            return None

        if self.history_index is None:
            self.history_draft = current_text
            self.history_index = len(self.command_history)

        if previous:
            if self.history_index > 0:
                self.history_index -= 1
            return self.command_history[self.history_index]

        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            return self.command_history[self.history_index]

        self.history_index = None
        return self.history_draft

    def _submit_command(self, command, source="input", record_history=True):
        if not self.connected:
            self.show_warning("请先登录设备")
            return

        raw_command = command if command is not None else ""
        command = self._normalize_display_command(raw_command)
        if not command and source == "console":
            self.console_edit.append_command("")
            self.console_edit.setFocus(Qt.OtherFocusReason)
            return

        if not command:
            return

        backend_command = self._build_backend_command(command)
        self._hide_history_suggestions()
        self._queue_stream_log_state_update(backend_command)
        self._executing_command = command if record_history else ""
        self.last_command_source = source
        self._last_command_failed = False
        self.command_running = True
        should_freeze_command_bar = source != "console"
        if should_freeze_command_bar:
            self.command_input.setEnabled(False)
            self.command_type_combo.setEnabled(False)
            self.add_shortcut_btn.setEnabled(False)
            self.toggle_shortcut_btn.setEnabled(False)
            self.update_send_button()
        if source == "console":
            self.console_edit.set_input_locked_quietly(True)
            self.console_edit.commit_console_submission_live(command)
        else:
            self.console_edit.commit_command_submission(command)
        QTimer.singleShot(
            0,
            lambda cmd=backend_command, timeout_ms=self.default_timeout_ms, download_root=self.download_root:
                self.request_command.emit(cmd, timeout_ms, download_root),
        )
        if source != "auto":
            self.command_input.clear()

    def on_worker_status_message(self, message):
        if not self._should_suppress_output(message):
            self.append_output(message)
        self.show_progress(message)

    def _format_connect_result_message(self, result: str, sn: str = "", detail: str = "", model: str = "") -> str:
        model = str(model or self.current_context.get("model") or "").strip()
        sn = str(sn or self.current_context.get("sn") or self.sn_input.text() or "").strip()
        if model and sn:
            suffix = f" [{model}] {sn}"
        elif sn:
            suffix = f" {sn}"
        elif model:
            suffix = f" [{model}]"
        else:
            suffix = ""
        detail = (detail or "").strip()
        if detail and sn:
            detail = detail.replace(f"设备：{sn}不在线", "设备不在线")
            detail = detail.replace(f"设备:{sn}不在线", "设备不在线")
            detail = detail.replace(f"设备 {sn} 不在线", "设备不在线")
        if detail == "设备不在线":
            detail = "设备离线"
        if detail:
            return f"{result}{suffix}: {detail}"
        return f"{result}{suffix}"

    def on_connected(self, context):
        self.connected = True
        self.connecting = False
        self.pending_target_sn = ""
        self.current_context = context
        self.sn_input.setText(context.get("sn", self.sn_input.text().strip()))
        self.sn_input.setEnabled(False)
        self.update_connect_button()
        self.console_edit.set_input_enabled(True)
        self.console_edit.set_input_locked(False)
        self.command_input.setEnabled(True)
        self.command_type_combo.setEnabled(True)
        self.update_shortcut_controls()
        self.update_send_button()
        success_message = self._format_connect_result_message(
            "连接成功",
            context.get("sn", ""),
            model=context.get("model", ""),
        )
        self.append_output(success_message)
        self._flush_pending_output()
        self.show_success(success_message)

    def on_connect_failed(self, message):
        failure_message = self._format_connect_result_message("连接失败", detail=message)
        self.connected = False
        self.connecting = False
        self.current_context = {}
        self._pending_stream_log_state = None
        self._last_command_failed = False
        self.sn_input.setEnabled(True)
        self.update_connect_button()
        self.console_edit.set_input_enabled(False)
        self.console_edit.set_input_locked(False)
        self.command_input.setEnabled(True)
        self.command_type_combo.setEnabled(True)
        self.update_shortcut_controls()
        self.update_send_button()
        self.append_output(failure_message, color=t("status_offline"))
        self.show_error(failure_message)

    def on_disconnected(self, message):
        disconnected_message = self._format_connect_result_message(message or "连接已断开")
        self.connected = False
        self.connecting = False
        self.command_running = False
        self._executing_command = ""
        self.current_context = {}
        self._stream_log_active = False
        self._pending_stream_log_state = None
        self._last_command_failed = False
        self._pending_output_entries = []
        self._pending_stream_log_entries = []
        self._output_flush_timer.stop()
        self._stream_log_flush_timer.stop()
        self.sn_input.setEnabled(True)
        self.update_connect_button()
        self.console_edit.set_input_enabled(False)
        self.console_edit.set_input_locked(False)
        self.command_input.setEnabled(True)
        self.command_type_combo.setEnabled(True)
        self.update_shortcut_controls()
        self.update_send_button()
        self._hide_history_suggestions()
        self.append_output(disconnected_message)
        self.show_info(disconnected_message)
        self._schedule_pending_connect()

    def on_command_failed(self, message):
        self._last_command_failed = True
        self._hide_history_suggestions()
        self.append_output(message, color=t("status_offline"))
        self.show_error(message)

    def on_command_progress(self, progress_id, message):
        if not message:
            return
        self.console_edit.update_progress(progress_id, message)

    def on_command_finished(self):
        self.command_running = False
        if not self._last_command_failed:
            self._record_successful_command(self._executing_command)
        self._executing_command = ""
        if self._pending_stream_log_state is not None and not self._last_command_failed:
            self._stream_log_active = self._pending_stream_log_state
        self._pending_stream_log_state = None
        self._last_command_failed = False
        if self.connected:
            if not self.console_edit._input_enabled:
                self.console_edit.set_input_enabled(True)
            else:
                self.console_edit.set_input_locked_quietly(False)
            if self.last_command_source != "console":
                self.command_input.setEnabled(True)
                self.command_type_combo.setEnabled(True)
                self.update_shortcut_controls()
                self.update_send_button()
            if self.last_command_source in ("console", "auto"):
                self.console_edit.setFocus(Qt.OtherFocusReason)
                if not self._stream_log_active:
                    self.console_edit.scroll_to_prompt()
            else:
                self.command_input.setFocus(Qt.OtherFocusReason)

    def on_console_clear_requested(self):
        self._console_suppress_until = time.monotonic() + 0.2
        self._hide_history_suggestions()
        self.console_edit.clear_console()
        self._pending_output_entries = []
        self._pending_stream_log_entries = []
        self._output_flush_timer.stop()
        self._stream_log_flush_timer.stop()

    def append_output(self, text, color=None):
        if not text:
            return
        if time.monotonic() < self._console_suppress_until:
            return
        self._pending_output_entries.append((str(text), color))
        if len(self._pending_output_entries) >= 20:
            self._flush_pending_output()
            return
        if not self._output_flush_timer.isActive():
            self._output_flush_timer.start()

    def append_stream_log_output(self, text):
        if not text:
            return
        if time.monotonic() < self._console_suppress_until:
            return
        self._pending_stream_log_entries.append(str(text))
        if len(self._pending_stream_log_entries) >= 10:
            self._flush_pending_stream_logs()
            return
        if not self._stream_log_flush_timer.isActive():
            self._stream_log_flush_timer.start()

    def _flush_pending_output(self):
        if time.monotonic() < self._console_suppress_until:
            self._pending_output_entries = []
            self._output_flush_timer.stop()
            return
        if not self._pending_output_entries:
            self._output_flush_timer.stop()
            return
        should_follow = self.console_edit._is_scrolled_to_bottom() and not self.console_edit._browse_mode
        pending = self._pending_output_entries
        self._pending_output_entries = []
        self._output_flush_timer.stop()
        for text, color in pending:
            self.console_edit.append_message(text, color=color)
        if self._stream_log_active:
            if should_follow:
                self.console_edit.scroll_to_prompt()
            return
        self.console_edit.scroll_to_prompt()

    def _flush_pending_stream_logs(self):
        if time.monotonic() < self._console_suppress_until:
            self._pending_stream_log_entries = []
            self._stream_log_flush_timer.stop()
            return
        if not self._pending_stream_log_entries:
            self._stream_log_flush_timer.stop()
            return
        pending = self._pending_stream_log_entries
        self._pending_stream_log_entries = []
        self._stream_log_flush_timer.stop()
        self.console_edit.append_stream_log_batch("\n".join(pending))

    def _queue_stream_log_state_update(self, command: str):
        if not is_startlogp2p_command(command):
            self._pending_stream_log_state = None
            return
        log_level = parse_startlogp2p_level(command)
        if log_level is None:
            self._pending_stream_log_state = None
            return
        self._pending_stream_log_state = log_level != 0

    def _should_suppress_output(self, message):
        message = (message or "").strip()
        if not message:
            return False
        if message in self.SUPPRESSED_CONNECT_MESSAGES:
            return True
        if any(message.startswith(prefix) for prefix in self.SUPPRESSED_CONNECT_PREFIXES):
            return True
        if message.startswith("开始连接设备:"):
            return True
        if message.startswith("已获取设备密码，目标设备:"):
            return True
        if message.startswith("设备：") and message.endswith("不在线"):
            return True
        return False

    def current_command_prefix(self):
        return str(self.command_type_combo.currentData() or self.command_type_combo.currentText() or "").strip()

    def _build_backend_command(self, command):
        command = (command or "").strip()
        prefix = self.current_command_prefix()
        if not prefix or not command:
            return command
        if is_syscmd_family_command(command) or is_getsystemcfg_command(command) or is_startlogp2p_command(command):
            return command
        if command == prefix or command.startswith(f"{prefix} "):
            return command
        return f"{prefix} {command}"

    def _normalize_display_command(self, command):
        command = (command or "").strip()
        if not command:
            return ""

        for _, prefix in self.COMMAND_TYPES:
            prefix = prefix.strip()
            if not prefix:
                continue
            if command == prefix:
                return ""
            if command.startswith(f"{prefix} "):
                return command[len(prefix):].strip()
        return command

    def refresh_shortcut_buttons(self):
        while self.shortcut_flow_layout.count() > 0:
            item = self.shortcut_flow_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for command in self.shortcut_commands:
            btn = DraggableShortcutButton(command)
            btn.setFixedHeight(self.SHORTCUT_CHIP_HEIGHT)
            btn.setFixedWidth(
                max(
                    self.SHORTCUT_MIN_BUTTON_WIDTH,
                    btn.fontMetrics().horizontalAdvance(command) + 24,
                )
            )
            btn.setToolTip(f"{command}\n左键发送，拖动可排序，右键可编辑或删除")
            btn.clicked.connect(lambda checked=False, cmd=command: self.on_shortcut_clicked(cmd))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, widget=btn, cmd=command: self.show_shortcut_context_menu(widget, pos, cmd)
            )
            btn.reorder_requested.connect(self.on_shortcut_reorder_requested)
            btn.setStyleSheet(self._get_shortcut_button_stylesheet())
            self.shortcut_flow_layout.addWidget(btn)

        self.update_shortcut_controls()
        self.refresh_shortcut_area_geometry()
        QTimer.singleShot(0, self.refresh_shortcut_area_geometry)

    def refresh_shortcut_area_geometry(self):
        if not hasattr(self, "shortcut_scroll") or self.shortcut_collapsed:
            return

        viewport = self.shortcut_scroll.viewport()
        viewport_width = max(1, viewport.width())
        viewport_height = max(1, viewport.height())
        self.shortcut_flow_layout.invalidate()
        content_height = max(1, self.shortcut_flow_layout.heightForWidth(viewport_width))

        self.shortcut_container.setMinimumSize(0, 0)
        self.shortcut_container.setMaximumSize(16777215, 16777215)
        self.shortcut_container.setFixedSize(viewport_width, content_height)
        self.shortcut_container.updateGeometry()
        self.shortcut_scroll.updateGeometry()
        scroll_bar = self.shortcut_scroll.verticalScrollBar()
        scroll_bar.setPageStep(viewport_height)
        scroll_bar.setRange(0, max(0, content_height - viewport_height))
        self._update_shortcut_hint_position()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_shortcut_area_geometry()

    def update_shortcut_controls(self):
        can_add = len(self.shortcut_commands) < self.MAX_SHORTCUTS and not self.connecting and not self.command_running
        self.add_shortcut_btn.setEnabled(can_add)
        self.toggle_shortcut_btn.setEnabled(not self.connecting and not self.command_running)

    def update_send_button(self):
        if self.command_running:
            self.send_btn.setEnabled(False)
            self.send_btn.setText("取消")
            self.send_btn.setToolTip("命令执行中")
            return

        self.send_btn.setEnabled(not self.connecting)
        self.send_btn.setText("发送")
        self.send_btn.setToolTip("发送命令")

    def update_connect_button(self):
        if self.canceling_connect:
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("取消")
            self.connect_btn.setIcon(QIcon(":/icons/common/connectting.png"))
            self.connect_btn.setToolTip("取消中...")
            return

        if self.connecting:
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("取消")
            self.connect_btn.setIcon(QIcon(":/icons/common/connectting.png"))
            self.connect_btn.setToolTip("取消")
            return

        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("登出" if self.connected else "登录")
        self.connect_btn.setIcon(
            QIcon(":/icons/common/disconnect.png") if self.connected else QIcon(":/icons/common/connect.png")
        )
        self.connect_btn.setToolTip("注销" if self.connected else "登录")

    def set_connecting_state(self, connecting):
        self.connecting = connecting
        if not connecting:
            self.canceling_connect = False
        self.sn_input.setEnabled(not connecting and not self.connected)
        self.console_edit.set_input_enabled(self.connected and not connecting)
        self.console_edit.set_input_locked(connecting or self.command_running)
        self.command_input.setEnabled(not connecting and not self.command_running)
        self.command_type_combo.setEnabled(not connecting and not self.command_running)
        self.update_shortcut_controls()
        self.update_send_button()
        self.update_connect_button()

    def cleanup(self):
        try:
            if hasattr(self, "worker"):
                QMetaObject.invokeMethod(self.worker, "shutdown", Qt.BlockingQueuedConnection)
        except Exception:
            pass

        if hasattr(self, "worker_thread"):
            self.worker_thread.quit()
            self.worker_thread.wait(3000)

    def fast_cleanup(self):
        try:
            if hasattr(self, "worker"):
                self.worker.cancel_pending_connect()
                QMetaObject.invokeMethod(self.worker, "shutdown", Qt.QueuedConnection)
        except Exception:
            pass

        if hasattr(self, "worker_thread"):
            try:
                self.worker_thread.quit()
                self.worker_thread.wait(500)
            except Exception:
                pass

    def refresh_theme(self):
        if hasattr(self, "connect_group"):
            self.connect_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        if hasattr(self, "command_group"):
            self.command_group.setStyleSheet(self._get_compact_group_box_stylesheet())
        for attr in ("_connect_frame", "_command_input_frame"):
            if hasattr(self, attr):
                self._apply_plain_toolbar_style(getattr(self, attr))
        if hasattr(self, "_shortcut_frame"):
            self._shortcut_frame.setStyleSheet(StyleManager.get_QUERY_FRAME())

        if hasattr(self, "console_edit"):
            self.console_edit.setStyleSheet(self._get_console_stylesheet())
            self.console_edit.refresh_content_style()
        if hasattr(self, "command_type_combo"):
            self.command_type_combo.setStyleSheet(StyleManager.get_COMBOBOX())
        if hasattr(self, "download_path_label"):
            self.download_path_label.setStyleSheet(self._get_download_path_label_stylesheet())
        if hasattr(self, "shortcut_hint_label"):
            self.shortcut_hint_label.setStyleSheet(self._get_shortcut_hint_stylesheet())
        if hasattr(self, "shortcut_scroll"):
            self.shortcut_scroll.setStyleSheet(StyleManager.get_SCROLL_AREA())
        if hasattr(self, "history_popup") and self.history_popup is not None:
            self.history_popup.refresh_theme()
        self.refresh_shortcut_buttons()

    def _update_shortcut_hint_position(self):
        if not hasattr(self, "shortcut_hint_label") or not hasattr(self, "shortcut_scroll"):
            return
        label_size = self.shortcut_hint_label.sizeHint()
        self.shortcut_hint_label.setGeometry(2, 2, label_size.width(), label_size.height())

    @staticmethod
    def _get_shortcut_hint_stylesheet():
        return f"""
        QLabel#shortcutHintLabel {{
            color: {t('text_hint')};
            background: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        }}
        QLabel#shortcutHintLabel:hover {{
            border: none;
        }}
        """

    @staticmethod
    def _default_download_root() -> str:
        desktop = Path.home() / "Desktop"
        if desktop.exists():
            return str(desktop)
        return str(Path.home())

    def _normalize_download_root(self, path: str) -> str:
        path = (path or "").strip()
        if not path:
            return self._default_download_root()
        return str(Path(path).expanduser())

    @staticmethod
    def _get_console_stylesheet():
        return f"""
        QTextEdit {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 0px;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 12px;
        }}
        QTextEdit:focus {{
            border: 1px solid {t('border_hover')};
            outline: none;
        }}
        QScrollBar:vertical {{
            background-color: {t('bg_dark')};
            width: 12px;
            border: none;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {t('border')};
            border-radius: 6px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {t('border_hover')};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        """

    @staticmethod
    def _get_download_path_label_stylesheet():
        return f"""
        QLabel {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 4px 6px;
        }}
        QLabel:hover {{
            border: 1px solid {t('border_hover')};
        }}
        """

    @staticmethod
    def _get_shortcut_button_stylesheet():
        return f"""
        QPushButton {{
            background-color: {t('bg_light')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            border-radius: 3px;
            padding: 2px 10px;
            text-align: left;
            font-size: 11px;
        }}
        QPushButton:hover {{
            background-color: {t('bg_hover')};
            border: 1px solid {t('border_hover')};
        }}
        """

    @staticmethod
    def _get_shortcut_context_menu_stylesheet():
        return f"""
        QMenu {{
            background-color: {t('bg_mid')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
            padding: 2px;
        }}
        QMenu::item {{
            padding: 6px 18px 6px 8px;
            margin: 1px 2px;
            border-radius: 2px;
        }}
        QMenu::item:selected {{
            background-color: {t('selection_bg')};
            color: {t('text_primary')};
        }}
        """
