"""A speech bubble beside the character for alerts (reminders, calendar and email notices)."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

BUBBLE_WIDTH = 260
SHOW_SECONDS = 12


class Bubble(QWidget):
    """Frameless, always-on-top note that fades after a few seconds; click it to dismiss.
    Several alerts in a row replace each other's text, with all of them kept in the log."""

    message_ready = Signal(str)  # alerts arrive on other threads; this queues them onto Qt

    def __init__(self, seconds: int = SHOW_SECONDS) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus  # an alert must not steal typing focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(BUBBLE_WIDTH)
        self.setObjectName("bubble")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            "QWidget#bubble { background: #fffbe6; border: 2px solid #c99700; border-radius: 12px; }"
            "QLabel { color: #2b2b2b; font-size: 13px; }"
        )
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.label)
        self._anchor: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(seconds * 1000)
        self._timer.timeout.connect(self.hide)
        self.message_ready.connect(self.show_message)

    def attach(self, anchor: QWidget) -> None:
        """Show bubbles next to `anchor` (the character)."""
        self._anchor = anchor

    def show_message(self, text: str) -> None:
        self.label.setText(text)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start()

    def _place(self) -> None:
        if self._anchor is None:
            return
        area = self._anchor.screen().availableGeometry()
        x = min(
            max(area.left(), self._anchor.x() + self._anchor.width() - self.width()),
            area.right() - self.width(),
        )
        above = self._anchor.y() - self.height() - 6
        y = above if above >= area.top() else self._anchor.y() + self._anchor.height() + 6
        self.move(x, y)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._timer.stop()
        self.hide()
