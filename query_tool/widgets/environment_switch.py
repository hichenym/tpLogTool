from PyQt5.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import QAbstractButton

from query_tool.utils.environment import normalize_environment, environment_label
from query_tool.utils.theme_manager import theme_manager, t


class EnvironmentSwitch(QAbstractButton):
    environment_changed = pyqtSignal(str)

    def __init__(self, parent=None, env='pro'):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(52, 28)
        self._position = 0.0
        self._press_x = 0.0
        self._press_position = 0.0
        self._dragging = False
        self._animation = QPropertyAnimation(self, b'thumb_position', self)
        self._animation.setDuration(140)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)
        theme_manager.theme_changed.connect(self.update)
        self.set_environment(env)

    @pyqtProperty(float)
    def thumb_position(self):
        return self._position

    @thumb_position.setter
    def thumb_position(self, value):
        self._position = max(0.0, min(1.0, value))
        self.update()

    def environment(self):
        return 'test' if self.isChecked() else 'pro'

    def set_environment(self, env):
        checked = normalize_environment(env) == 'test'
        self._animation.stop()
        blocked = self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(blocked)
        self.thumb_position = float(checked)
        self._update_label()

    def _update_label(self):
        self.setText('测试' if self.isChecked() else '正式')
        label = environment_label(self.environment())
        self.setAccessibleName(f'平台切换，当前{label}')
        self.setToolTip(f'当前：{label}；左侧正式，右侧测试，点击或拖动切换')

    def _animate(self):
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(float(self.isChecked()))
        self._animation.start()

    def _on_toggled(self, checked):
        self._update_label()
        self._animate()
        self.environment_changed.emit(self.environment())

    def _track_rect(self):
        height = min(18, self.height() - 10)
        return QRectF(0.5, (self.height() - height) / 2, self.width() - 1, height)

    def _thumb_rect(self):
        diameter = self._track_rect().height() - 4
        travel = max(1, self.width() - diameter - 4)
        return QRectF(2 + travel * self._position, (self.height() - diameter) / 2, diameter, diameter)

    def _text_rect(self):
        diameter = self._thumb_rect().width()
        width = max(0, self.width() - diameter - 10)
        left = 4 if self.isChecked() else diameter + 6
        return QRectF(left, 0, width, self.height())

    def _text_font(self):
        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(False)
        return font

    def _track_color(self):
        return QColor(t('platform_test_bg') if self.isChecked() else t('accent_dim'))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        if self.underMouse() or self.isDown():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(t('bg_mid') if self.isDown() else t('bg_hover')))
            painter.drawRoundedRect(QRectF(self.rect()), 3, 3)
        track = self._track_rect()
        painter.setPen(QPen(QColor(t('status_info') if self.hasFocus() else t('border')), 1))
        painter.setBrush(self._track_color())
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        text_color = t('text_primary') if theme_manager.is_dark else t('bg_light')
        painter.setPen(QColor(text_color))
        painter.setFont(self._text_font())
        painter.drawText(self._text_rect(), Qt.AlignCenter, self.text())
        thumb = self._thumb_rect()
        knob_color = QColor(t('text_primary') if theme_manager.is_dark else t('bg_light'))
        painter.setPen(QPen(QColor(t('border')), 0.7))
        painter.setBrush(knob_color)
        painter.drawEllipse(thumb)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._press_x = event.x()
        self._press_position = self._position
        self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isDown() and abs(event.x() - self._press_x) > 3:
            self._dragging = True
            self._animation.stop()
            travel = max(1, self.width() - self._thumb_rect().width() - 4)
            self.thumb_position = self._press_position + (event.x() - self._press_x) / travel
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self.setDown(False)
            if self.rect().contains(event.pos()):
                self.setChecked(self._position >= 0.5)
            self._animate()
            self._dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_Right):
            self.setChecked(event.key() == Qt.Key_Right)
            event.accept()
        else:
            super().keyPressEvent(event)
