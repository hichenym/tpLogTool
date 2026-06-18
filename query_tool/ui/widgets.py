"""Common widget aliases for the Fluent migration."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPalette
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTextEdit,
)

from query_tool.utils.theme_manager import t, theme_manager


class _UnifiedLabel(QLabel):
    FONT_PIXEL_SIZE = 14
    FONT_WEIGHT = QFont.Normal
    _BASE_STYLESHEET = "background: transparent; background-color: transparent; border: none; padding: 0px; margin: 0px;"

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._init_label()

    def _init_label(self):
        font = self.font()
        font.setPixelSize(self.FONT_PIXEL_SIZE)
        font.setWeight(self.FONT_WEIGHT)
        self.setFont(font)
        self.setWordWrap(True)
        self.setTextFormat(Qt.AutoText)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        super().setStyleSheet(self._BASE_STYLESHEET)
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)
        self.destroyed.connect(self._disconnect_theme)

    def setStyleSheet(self, style: str):
        """Keep labels transparent by default unless a caller explicitly overrides it."""
        style = style or ""
        if style.strip():
            super().setStyleSheet(f"{self._BASE_STYLESHEET} {style}")
        else:
            super().setStyleSheet(self._BASE_STYLESHEET)

    def _disconnect_theme(self):
        try:
            theme_manager.theme_changed.disconnect(self._apply_theme)
        except Exception:
            pass

    def _text_minimum_width(self):
        text = self.text()
        if not text or self.wordWrap():
            return 0
        metrics = QFontMetrics(self.font())
        return metrics.horizontalAdvance(text.replace("\n", " ")) + 4

    def _text_minimum_height(self):
        metrics = QFontMetrics(self.font())
        lines = max(1, self.text().count("\n") + 1)
        return metrics.lineSpacing() * lines + 4

    def _apply_theme(self):
        self.setGraphicsEffect(None)
        palette = self.palette()
        palette.setColor(QPalette.WindowText, QColor(t('text_primary')))
        self.setPalette(palette)
        self.updateGeometry()

    def setFixedHeight(self, h: int):
        super().setFixedHeight(max(int(h), self._text_minimum_height()))

    def setFixedWidth(self, w: int):
        super().setFixedWidth(max(int(w), self._text_minimum_width()))

    def setFixedSize(self, *args):
        if len(args) == 1:
            size = args[0]
            width = size.width()
            height = size.height()
        else:
            width, height = args
        super().setFixedSize(
            max(int(width), self._text_minimum_width()),
            max(int(height), self._text_minimum_height()),
        )

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setHeight(max(hint.height(), self._text_minimum_height()))
        return hint

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), self._text_minimum_height()))
        return hint


class BodyLabel(_UnifiedLabel):
    FONT_PIXEL_SIZE = 14
    FONT_WEIGHT = QFont.Normal


class StrongBodyLabel(_UnifiedLabel):
    FONT_PIXEL_SIZE = 14
    FONT_WEIGHT = QFont.DemiBold


class SubtitleLabel(_UnifiedLabel):
    FONT_PIXEL_SIZE = 20
    FONT_WEIGHT = QFont.DemiBold

try:
    from qfluentwidgets import (
        Action,
        CardWidget,
        CheckBox,
        ComboBox,
        DateEdit,
        EditableComboBox,
        LineEdit,
        PasswordLineEdit,
        Pivot,
        PlainTextEdit,
        PrimaryPushButton,
        ProgressBar,
        PushButton,
        RadioButton,
        RoundMenu,
        ScrollArea,
        SimpleCardWidget as _QFluentSimpleCardWidget,
        TableWidget,
        TextEdit,
        ElevatedCardWidget as _QFluentElevatedCardWidget,
    )

    class ElevatedCardWidget(_QFluentElevatedCardWidget):
        """Disable Fluent hover lift/shadow animation for page group cards."""

        def __init__(self, parent=None):
            super().__init__(parent)
            if hasattr(self, "shadowAni") and self.shadowAni is not None:
                self.removeEventFilter(self.shadowAni)
                self.shadowAni.deleteLater()
                self.shadowAni = None
            self.setGraphicsEffect(None)

        def enterEvent(self, e):
            _QFluentSimpleCardWidget.enterEvent(self, e)

        def leaveEvent(self, e):
            _QFluentSimpleCardWidget.leaveEvent(self, e)

        def mousePressEvent(self, e):
            _QFluentSimpleCardWidget.mousePressEvent(self, e)

    QFLUENT_WIDGETS_AVAILABLE = True
    SpinBox = QSpinBox
except Exception:
    QFLUENT_WIDGETS_AVAILABLE = False

    Action = None
    PushButton = QPushButton
    PrimaryPushButton = QPushButton
    LineEdit = QLineEdit
    PasswordLineEdit = QLineEdit
    ComboBox = QComboBox
    EditableComboBox = QComboBox
    CheckBox = QCheckBox
    RadioButton = QRadioButton
    ScrollArea = QScrollArea
    SpinBox = QSpinBox
    TableWidget = QTableWidget
    ProgressBar = QProgressBar
    PlainTextEdit = QPlainTextEdit
    TextEdit = QTextEdit
    CardWidget = QFrame
    ElevatedCardWidget = QFrame
    DateEdit = QDateEdit
    RoundMenu = None

    class Pivot(QFrame):  # pragma: no cover - runtime guard only
        def addItem(self, *_args, **_kwargs):
            raise RuntimeError("qfluentwidgets is not installed")

        def setCurrentItem(self, *_args, **_kwargs):
            raise RuntimeError("qfluentwidgets is not installed")
