"""A small text box next to the character: type a request, read the reply."""

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

POPUP_WIDTH = 320
THINKING_TEXT = "..."


class InputPopup(QWidget):
    """Frameless, always-on-top box. Enter sends the text to `submit`. Close it with the X in the
    corner or Esc; drag it by its title or any empty part to move it (it then reopens there)."""

    reply_ready = Signal(str)  # replies come from the chat thread; this queues them onto Qt
    expand_requested = Signal()  # the user wants the full chat window

    def __init__(self, submit: Callable[[str], None]) -> None:
        super().__init__()
        self._submit = submit
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedWidth(POPUP_WIDTH)
        self.setStyleSheet(
            "QWidget#box { background: #202124; border-radius: 10px; }"
            "QLineEdit { background: #303134; color: #e8eaed; border: none; padding: 6px;"
            " border-radius: 6px; }"
            "QLabel { color: #e8eaed; }"
            "QPushButton { background: transparent; color: #9aa0a6; border: none;"
            " font-size: 14px; padding: 0 4px; }"
            "QPushButton:hover { color: #ffffff; background: #d93025; border-radius: 4px; }"
        )
        self.setObjectName("box")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._drag_offset: QPoint | None = None
        self._drag_start = QPoint()
        self._moved_to: QPoint | None = None  # where the user last left it
        title = QLabel("Jarvis")
        title.setStyleSheet("color: #9aa0a6; font-weight: bold;")
        self.expand_button = QPushButton("⤢")
        self.expand_button.setToolTip("Open the chat window")
        self.expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_button.clicked.connect(self.expand_requested)
        self.close_button = QPushButton("✕")
        self.close_button.setToolTip("Close")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.hide)
        header = QHBoxLayout()
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.expand_button)
        header.addWidget(self.close_button)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis...")
        self.input.returnPressed.connect(self._send)
        self.reply = QLabel()
        self.reply.setWordWrap(True)
        self.reply.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reply.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addLayout(header)
        layout.addWidget(self.input)
        layout.addWidget(self.reply)
        self.reply_ready.connect(self.show_reply)

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.show_reply(THINKING_TEXT)
        self._submit(text)

    def show_reply(self, text: str) -> None:
        self.reply.setText(text)
        self.reply.setVisible(bool(text))
        self.adjustSize()

    def open_near(self, anchor: QWidget) -> None:
        """Show the popup beside `anchor` (the character), kept on screen."""
        self.adjustSize()
        if self._moved_to is not None:
            self.move(self._moved_to)
            self._focus()
            return
        area = anchor.screen().availableGeometry()
        x = min(
            max(area.left(), anchor.x() + anchor.width() - self.width()),
            area.right() - self.width(),
        )
        above = anchor.y() - self.height() - 6
        y = above if above >= area.top() else anchor.y() + anchor.height() + 6
        self.move(x, y)
        self._focus()

    def _focus(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self.pos()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            if self.pos() != self._drag_start:  # a plain click on the background is not a move
                self._moved_to = self.pos()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
