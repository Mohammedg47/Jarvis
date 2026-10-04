"""The Yes/No popup for risky actions. Its buttons answer through the same input line as typing
or saying "yes", so whichever comes first wins."""

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def describe(name: str, arguments: dict) -> str:
    """A plain-words line for a tool call, e.g. 'close app: name = notepad'."""
    args = ", ".join(f"{k} = {v}" for k, v in arguments.items())
    return f"{name.replace('_', ' ')}" + (f": {args}" if args else "")


class ConfirmDialog(QWidget):
    """Frameless, always-on-top question with Yes and No. Closing it counts as No."""

    question_ready = Signal(str)  # the worker thread asks through these two signals
    dismiss_ready = Signal()

    def __init__(self, answer: Callable[[bool], None]) -> None:
        super().__init__()
        self._answer = answer
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedWidth(340)
        self.setObjectName("box")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet(
            "QWidget#box { background: #202124; border: 2px solid #f9ab00; border-radius: 10px; }"
            "QLabel { color: #e8eaed; }"
            "QPushButton { background: #303134; color: #e8eaed; border: none; padding: 8px 18px;"
            " border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #3c4043; }"
            "QPushButton#yes { background: #1e8e3e; } QPushButton#yes:hover { background: #188038; }"
            "QPushButton#no { background: #d93025; } QPushButton#no:hover { background: #c5221f; }"
        )
        self.title = QLabel("Jarvis needs your OK")
        self.title.setStyleSheet("color: #f9ab00; font-weight: bold;")
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.yes = QPushButton("Yes")
        self.yes.setObjectName("yes")
        self.no = QPushButton("No")
        self.no.setObjectName("no")
        self.yes.clicked.connect(lambda: self._finish(True))
        self.no.clicked.connect(lambda: self._finish(False))
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.no)
        buttons.addWidget(self.yes)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self.title)
        layout.addWidget(self.text)
        layout.addLayout(buttons)
        self.question_ready.connect(self.ask)
        self.dismiss_ready.connect(self.hide)

    def ask(self, question: str) -> None:
        self.text.setText(question)
        self.adjustSize()
        area = self.screen().availableGeometry()
        self.move(area.center().x() - self.width() // 2, area.top() + area.height() // 4)
        self.show()
        self.raise_()
        self.activateWindow()
        self.yes.setFocus()

    def _finish(self, yes: bool) -> None:
        self.hide()
        self._answer(yes)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._finish(False)
        else:
            super().keyPressEvent(event)
