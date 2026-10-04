"""The animated face: drawn with QPainter, one look per personality, one animation per state.

`pose(state, t)` says what the face is doing at time `t` (pure, so it is easy to test) and
`paint_face` draws it, so the floating window and the tray icon share the same drawing.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QMovie, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from jarvis.core.events import State

# Premade skin: Google's Noto Animated Emoji (CC BY 4.0, see jarvis/ui/skins/noto/LICENSE.txt),
# one GIF per state and personality. "drawn" selects the code-drawn face below instead.
NOTO_DIR = Path(__file__).parent / "skins" / "noto"
NOTO = {
    "playful": {
        State.IDLE: "1f642",  # slightly smiling face
        State.LISTENING: "1f442",  # ear
        State.THINKING: "1f914",  # thinking face
        State.SPEAKING: "1f604",  # grinning face
    },
    "formal": {
        State.IDLE: "1f610",  # neutral face
        State.LISTENING: "1f442",
        State.THINKING: "1f9d0",  # face with monocle
        State.SPEAKING: "1f5e3",  # speaking head
    },
}
STYLE = "noto"


def set_style(style: str) -> None:
    global STYLE
    STYLE = style


def noto_path(state: State, personality: str) -> Path | None:
    """The GIF for this state, or None when the drawn face should be used."""
    if STYLE != "noto":
        return None
    path = NOTO_DIR / f"{NOTO.get(personality, NOTO['playful'])[state]}.gif"
    return path if path.exists() else None


FACE_SIZE = 120
FRAME_MS = 33  # about 30 frames per second
BLINK_EVERY = 4.0  # seconds between blinks
BLINK_FOR = 0.15


@dataclass(frozen=True)
class Pose:
    bob: float  # vertical offset in units of the face radius
    eye_open: float  # 0 closed .. 1 normal .. 1.25 wide
    look_x: float  # where the pupils point, -1 .. 1
    look_y: float
    mouth: float  # 0 closed .. 1 wide open
    ring: float  # 0 none, otherwise the pulse phase 0..1 of the listening ring
    dots: int  # thinking dots lit (0 to 3)


def pose(state: State, t: float) -> Pose:
    """What the face looks like `t` seconds into the animation for `state`."""
    blinking = (t % BLINK_EVERY) < BLINK_FOR
    if state == State.LISTENING:
        # Wide eyes, looking at the user, with a ring that pulses outwards.
        return Pose(0.0, 1.25, 0.0, 0.0, 0.15, (t * 0.9) % 1.0, 0)
    if state == State.THINKING:
        # Eyes drift up and sideways, and three dots light up one by one.
        sway = math.sin(t * 1.6)
        return Pose(0.0, 1.0, 0.5 * sway, -0.7, 0.0, 0.0, int(t * 2.5) % 4)
    if state == State.SPEAKING:
        # The mouth opens and closes at an uneven, speech-like rhythm.
        mouth = abs(math.sin(t * 9.0)) * (0.55 + 0.45 * abs(math.sin(t * 3.7)))
        return Pose(0.02 * math.sin(t * 9.0), 1.0, 0.0, 0.0, mouth, 0.0, 0)
    # Idle: a slow float and an occasional blink.
    return Pose(0.05 * math.sin(t * 2.0), 0.1 if blinking else 1.0, 0.0, 0.0, 0.0, 0.0, 0)


# (face fill, outline, cheek) per personality; the formal one is a calmer blue-grey.
LOOKS = {
    "playful": (QColor("#FFD54A"), QColor("#C99700"), QColor("#FF9E80")),
    "formal": (QColor("#9FB3C8"), QColor("#4F6479"), QColor("#9FB3C8")),
}
INK = QColor("#2B2B2B")


def paint_face(painter: QPainter, rect: QRectF, p: Pose, personality: str = "playful") -> None:
    """Draw the face filling `rect` (square) in pose `p`."""
    fill, outline, cheek = LOOKS.get(personality, LOOKS["playful"])
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = rect.width() / 2 * 0.78  # leave room for the ring and the dots
    centre = QPointF(rect.center().x(), rect.center().y() + p.bob * r)

    if p.ring > 0:
        ring = QColor(outline)
        ring.setAlphaF(max(0.0, 0.8 * (1 - p.ring)))
        painter.setPen(QPen(ring, max(2.0, r * 0.06)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        grow = r * (1.0 + 0.28 * p.ring)
        painter.drawEllipse(centre, grow, grow)

    painter.setPen(QPen(outline, max(2.0, r * 0.07)))
    painter.setBrush(QBrush(fill))
    painter.drawEllipse(centre, r, r)

    if personality == "playful":  # rosy cheeks
        painter.setPen(Qt.PenStyle.NoPen)
        blush = QColor(cheek)
        blush.setAlphaF(0.55)
        painter.setBrush(blush)
        for side in (-1, 1):
            painter.drawEllipse(
                QPointF(centre.x() + side * r * 0.58, centre.y() + r * 0.28), r * 0.14, r * 0.09
            )

    eye_r = r * 0.17
    for side in (-1, 1):
        eye = QPointF(centre.x() + side * r * 0.38, centre.y() - r * 0.18)
        height = max(eye_r * 2 * p.eye_open, r * 0.04)
        painter.setPen(QPen(outline, max(1.5, r * 0.04)))
        painter.setBrush(QColor("white"))
        painter.drawEllipse(eye, eye_r, height / 2)
        if p.eye_open > 0.3:  # pupils vanish behind a closed eyelid
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(INK)
            pupil = QPointF(eye.x() + p.look_x * eye_r * 0.45, eye.y() + p.look_y * eye_r * 0.45)
            painter.drawEllipse(pupil, eye_r * 0.5, min(eye_r * 0.5, height * 0.4))

    if personality == "formal":  # round glasses
        painter.setPen(QPen(INK, max(1.5, r * 0.035)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for side in (-1, 1):
            painter.drawEllipse(
                QPointF(centre.x() + side * r * 0.38, centre.y() - r * 0.18),
                eye_r * 1.55,
                eye_r * 1.55,
            )
        painter.drawLine(
            QPointF(centre.x() - r * 0.38 + eye_r * 1.55, centre.y() - r * 0.18),
            QPointF(centre.x() + r * 0.38 - eye_r * 1.55, centre.y() - r * 0.18),
        )

    _paint_mouth(painter, centre, r, p, personality)

    if p.dots:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(outline)
        for i in range(3):
            lit = i < p.dots
            painter.setOpacity(1.0 if lit else 0.25)
            painter.drawEllipse(
                QPointF(rect.center().x() + (i - 1) * r * 0.3, rect.top() + r * 0.12),
                r * 0.08,
                r * 0.08,
            )
    painter.restore()


def _paint_mouth(painter: QPainter, c: QPointF, r: float, p: Pose, personality: str) -> None:
    painter.setPen(QPen(INK, max(2.0, r * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    mouth_y = c.y() + r * 0.42
    if p.mouth > 0.12:  # open: an ellipse that grows with the openness
        painter.setBrush(QColor("#7A1F1F"))
        painter.drawEllipse(QPointF(c.x(), mouth_y), r * 0.22, r * (0.04 + 0.2 * p.mouth))
        return
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if personality == "formal":  # a level, composed line
        painter.drawLine(QPointF(c.x() - r * 0.2, mouth_y), QPointF(c.x() + r * 0.2, mouth_y))
        return
    smile = QPainterPath(QPointF(c.x() - r * 0.28, mouth_y - r * 0.04))  # playful: a smile
    smile.quadTo(QPointF(c.x(), mouth_y + r * 0.3), QPointF(c.x() + r * 0.28, mouth_y - r * 0.04))
    painter.drawPath(smile)


def render_icon(
    state: State, personality: str = "playful", t: float = 0.0, size: int = 64
) -> QIcon:
    """A still frame of the face, for the tray icon."""
    gif = noto_path(state, personality)
    if gif is not None:
        movie = QMovie(str(gif))
        movie.jumpToFrame(0)
        return QIcon(
            movie.currentPixmap().scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    paint_face(painter, QRectF(0, 0, size, size), pose(state, t), personality)
    painter.end()
    return QIcon(pixmap)


class FaceWidget(QWidget):
    """Draws and animates the face. Only runs its timer while there is something to see."""

    def __init__(self, personality: str = "playful") -> None:
        super().__init__()
        self.setFixedSize(FACE_SIZE, FACE_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.state = State.IDLE
        self.personality = personality
        self.t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(lambda: self.tick(FRAME_MS / 1000))
        self._movie: QMovie | None = None
        self._load_movie()

    def _load_movie(self) -> None:
        """Switch to the GIF for the current state and personality (if the skin has one)."""
        if self._movie is not None:
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None
        gif = noto_path(self.state, self.personality)
        if gif is not None:
            self._movie = QMovie(str(gif), parent=self)
            self._movie.frameChanged.connect(lambda _: self.update())
            if self.isVisible():
                self._movie.start()

    def set_state(self, state: State) -> None:
        if state != self.state:
            self.state = state
            self.t = 0.0  # every state starts its animation from the beginning
            self._load_movie()
            self.update()

    def set_personality(self, personality: str) -> None:
        self.personality = personality
        self._load_movie()
        self.update()

    def tick(self, dt: float) -> None:
        self.t += dt
        self.update()

    def showEvent(self, event) -> None:
        self._timer.start()
        if self._movie is not None:
            self._movie.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        if self._movie is not None:
            self._movie.setPaused(True)
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if self._movie is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            painter.drawPixmap(self.rect(), self._movie.currentPixmap())
            painter.end()
            return
        paint_face(painter, QRectF(self.rect()), pose(self.state, self.t), self.personality)
        painter.end()
