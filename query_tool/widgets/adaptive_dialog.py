from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QDialog, QFrame, QVBoxLayout, QWidget

from query_tool.ui import ScrollArea
from query_tool.utils import StyleManager


def _coerce_size(size, fallback: QSize) -> QSize:
    if isinstance(size, QSize):
        return QSize(size)
    if isinstance(size, (tuple, list)) and len(size) == 2:
        return QSize(int(size[0]), int(size[1]))
    return QSize(fallback)


class AdaptiveDialog(QDialog):
    """Provide a consistent screen-aware size policy for project dialogs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preferred_dialog_size = None
        self._minimum_dialog_size = QSize(320, 200)
        self._dialog_max_width_ratio = 0.92
        self._dialog_max_height_ratio = 0.90
        self._dialog_margin = QSize(24, 24)
        self._adaptive_size_initialized = False
        self._adaptive_scroll_area = None
        self._adaptive_content_widget = None
        self._adapt_on_show = True

    def init_dialog_layout(
        self,
        preferred_size,
        min_size=(320, 200),
        *,
        scrollable=False,
        layout_margins=(20, 20, 20, 20),
        spacing=12,
        max_width_ratio=0.92,
        max_height_ratio=0.90,
    ):
        self._preferred_dialog_size = _coerce_size(preferred_size, QSize(640, 480))
        self._minimum_dialog_size = _coerce_size(min_size, QSize(320, 200))
        self._dialog_max_width_ratio = max_width_ratio
        self._dialog_max_height_ratio = max_height_ratio
        self.setSizeGripEnabled(True)

        if scrollable:
            root_layout = QVBoxLayout(self)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(0)

            scroll_area = ScrollArea(self)
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.NoFrame)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setStyleSheet(StyleManager.get_SCROLL_AREA())

            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(*layout_margins)
            content_layout.setSpacing(spacing)

            scroll_area.setWidget(content_widget)
            root_layout.addWidget(scroll_area)

            self._adaptive_scroll_area = scroll_area
            self._adaptive_content_widget = content_widget
            self.apply_adaptive_geometry()
            return content_layout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*layout_margins)
        layout.setSpacing(spacing)
        self.apply_adaptive_geometry()
        return layout

    def _available_geometry(self):
        app = QApplication.instance()
        desktop = app.desktop() if app is not None else None
        if desktop is None:
            return None

        parent = self.parentWidget()
        if parent is not None:
            return desktop.availableGeometry(parent.window())
        if self.isVisible():
            return desktop.availableGeometry(self)

        cursor_pos = QCursor.pos()
        screen_number = desktop.screenNumber(cursor_pos)
        return desktop.availableGeometry(screen_number)

    def apply_adaptive_geometry(self):
        if self._preferred_dialog_size is None:
            return

        available = self._available_geometry()
        if available is None:
            return

        max_width = max(240, available.width() - self._dialog_margin.width())
        max_height = max(180, available.height() - self._dialog_margin.height())

        preferred_width = min(
            self._preferred_dialog_size.width(),
            int(available.width() * self._dialog_max_width_ratio),
            max_width,
        )
        preferred_height = min(
            self._preferred_dialog_size.height(),
            int(available.height() * self._dialog_max_height_ratio),
            max_height,
        )

        min_width = min(self._minimum_dialog_size.width(), max_width)
        min_height = min(self._minimum_dialog_size.height(), max_height)

        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)

        if not self._adaptive_size_initialized:
            self.resize(max(min_width, preferred_width), max(min_height, preferred_height))
            self._adaptive_size_initialized = True
            return

        current = self.size()
        bounded_width = min(max(current.width(), min_width), max_width)
        bounded_height = min(max(current.height(), min_height), max_height)
        if bounded_width != current.width() or bounded_height != current.height():
            self.resize(bounded_width, bounded_height)

    def showEvent(self, event):
        super().showEvent(event)
        if self._adapt_on_show:
            QTimer.singleShot(0, self.apply_adaptive_geometry)

    def lock_size_to_current(self):
        current_size = self.size()
        self.setFixedSize(current_size)
        self.setSizeGripEnabled(False)
