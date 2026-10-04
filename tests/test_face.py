from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from jarvis.core.events import State
from jarvis.ui.face import BLINK_EVERY, FaceWidget, paint_face, pose, render_icon


def test_each_state_has_its_own_animation():
    idle, listening = pose(State.IDLE, 1.0), pose(State.LISTENING, 1.0)
    thinking, speaking = pose(State.THINKING, 1.0), pose(State.SPEAKING, 0.2)
    assert listening.ring > 0 and listening.eye_open > idle.eye_open
    assert thinking.dots > 0 and thinking.look_y < 0
    assert speaking.mouth > 0.1
    assert idle.mouth == 0 and idle.ring == 0 and idle.dots == 0


def test_speaking_mouth_moves_over_time():
    mouths = {round(pose(State.SPEAKING, i * 0.05).mouth, 2) for i in range(40)}
    assert len(mouths) > 10 and max(mouths) > 0.3 and min(mouths) < 0.1


def test_thinking_dots_cycle_and_idle_blinks():
    assert {pose(State.THINKING, i * 0.2).dots for i in range(20)} == {0, 1, 2, 3}
    assert pose(State.IDLE, 0.0).eye_open < 0.3  # a blink at the start of each period
    assert pose(State.IDLE, BLINK_EVERY / 2).eye_open == 1.0


def test_every_state_and_personality_paints_something():
    for personality in ("playful", "formal"):
        for state in State:
            image = QImage(120, 120, QImage.Format.Format_ARGB32)
            image.fill(0)
            painter = QPainter(image)
            paint_face(painter, QRectF(0, 0, 120, 120), pose(state, 0.3), personality)
            painter.end()
            assert any(image.pixelColor(x, 60).alpha() for x in range(120))


def test_personalities_look_different():
    def centre_colour(personality):
        image = QImage(120, 120, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        paint_face(painter, QRectF(0, 0, 120, 120), pose(State.IDLE, 1.0), personality)
        painter.end()
        return image.pixelColor(60, 30).name()

    assert centre_colour("playful") != centre_colour("formal")


def test_widget_restarts_its_animation_on_a_state_change_and_ticks():
    from jarvis.ui.character import QApplication

    QApplication.instance() or QApplication([])
    widget = FaceWidget()
    widget.tick(0.5)
    assert widget.t == 0.5
    widget.set_state(State.SPEAKING)
    assert widget.t == 0.0 and widget.state == State.SPEAKING


def test_tray_icon_renders_for_every_state():
    from jarvis.ui.character import QApplication

    QApplication.instance() or QApplication([])
    assert all(not render_icon(state).isNull() for state in State)


def test_every_state_has_a_premade_gif_and_drawn_style_skips_them():
    from jarvis.ui import face

    for personality in ("playful", "formal"):
        for state in State:
            assert face.noto_path(state, personality) is not None
    face.set_style("drawn")
    try:
        assert face.noto_path(State.IDLE, "playful") is None
    finally:
        face.set_style("noto")


def test_widget_switches_gif_with_state_and_personality():
    from jarvis.ui.character import QApplication

    QApplication.instance() or QApplication([])
    widget = FaceWidget()
    idle = widget._movie.fileName()
    widget.set_state(State.THINKING)
    assert widget._movie.fileName() != idle
    widget.set_personality("formal")
    assert widget._movie.fileName().endswith("1f9d0.gif")
