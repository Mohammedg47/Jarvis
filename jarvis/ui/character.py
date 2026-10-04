"""The floating character: a transparent, frameless, always-on-top animated face."""

import json
import logging
import random
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from jarvis.core.events import State
from jarvis.ui.face import FaceWidget

logger = logging.getLogger("jarvis.character")

SCREEN_MARGIN = 40
ROAM_EVERY_MS = 20_000  # how often an idle character wanders to a new spot
ROAM_GLIDE_MS = 3_000


def load_position(path: Path) -> QPoint | None:
    """The saved window position, or None if there is none or the file is unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return QPoint(int(data["x"]), int(data["y"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_position(path: Path, point: QPoint) -> None:
    try:
        path.write_text(json.dumps({"x": point.x(), "y": point.y()}), encoding="utf-8")
    except OSError:
        logger.warning("Could not save the character position to %s", path)


class CharacterWindow(QWidget):
    # Bus events arrive on other threads; a signal queues them onto the Qt thread.
    state_changed = Signal(State)
    personality_changed = Signal(str)
    clicked = Signal()  # a press and release without dragging

    def __init__(
        self,
        position_file: Path | None = None,
        roam: bool = False,
        personality: str = "playful",
    ) -> None:
        super().__init__()
        self._personality = personality
        self._position_file = position_file
        self._drag_offset: QPoint | None = None
        self._drag_start: QPoint | None = None
        self._state = State.IDLE
        self._glide = QPropertyAnimation(self, b"pos")
        self._glide.setDuration(ROAM_GLIDE_MS)
        self._glide.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._roam_timer = QTimer(self)
        self._roam_timer.setInterval(ROAM_EVERY_MS)
        self._roam_timer.timeout.connect(self.roam_once)
        self.set_roaming(roam)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # no taskbar button
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.face = FaceWidget(personality)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.face)
        self.state_changed.connect(self.show_state)
        self.personality_changed.connect(self.set_personality)

    @property
    def state(self) -> State:
        return self._state

    @property
    def personality(self) -> str:
        return self._personality

    def set_personality(self, personality: str) -> None:
        """Switch to that personality's look (each personality has its own face)."""
        self._personality = personality
        self.face.set_personality(personality)

    @property
    def roaming(self) -> bool:
        return self._roam_timer.isActive()

    def set_roaming(self, roam: bool) -> None:
        if roam:
            self._roam_timer.start()
        else:
            self._roam_timer.stop()
            self._glide.stop()

    def show_state(self, state: State) -> None:
        self._state = state
        self.face.set_state(state)
        if state != State.IDLE:
            self._glide.stop()  # stay put while Jarvis is busy

    def roam_once(self) -> None:
        """Glide to a random spot on this screen. Only when idle and not being dragged.
        The window is just the face, so the rest of the screen stays clickable, and the
        wandering spot is never saved (only a drag by the user is)."""
        if self._state != State.IDLE or self._drag_offset is not None:
            return
        area = self.screen().availableGeometry()
        x = random.randint(area.left(), max(area.left(), area.right() - self.width()))
        y = random.randint(area.top(), max(area.top(), area.bottom() - self.height()))
        self._glide.stop()
        self._glide.setStartValue(self.pos())
        self._glide.setEndValue(QPoint(x, y))
        self._glide.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._glide.stop()
            self._drag_start = self.pos()
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            if self.pos() == self._drag_start:
                self.clicked.emit()
            elif self._position_file is not None:
                save_position(self._position_file, self.pos())

    def place(self) -> None:
        """Restore the saved position if it is still on a screen, else bottom right."""
        self.adjustSize()
        saved = load_position(self._position_file) if self._position_file else None
        if saved is not None and QApplication.screenAt(saved) is not None:
            self.move(saved)
        else:
            self.place_bottom_right()

    def place_bottom_right(self) -> None:
        area = self.screen().availableGeometry()
        self.adjustSize()
        self.move(
            area.right() - self.width() - SCREEN_MARGIN,
            area.bottom() - self.height() - SCREEN_MARGIN,
        )
