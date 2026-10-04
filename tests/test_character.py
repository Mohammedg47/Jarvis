from jarvis.core.events import EventBus, State
from jarvis.ui.character import SKINS


def test_every_state_has_a_distinct_emoji():
    assert set(SKINS["playful"]) == set(State)
    assert len(set(SKINS["playful"].values())) == len(State)


def test_bus_updates_the_window_label():
    from jarvis.ui.character import CharacterWindow, QApplication

    app = QApplication.instance() or QApplication([])
    window = CharacterWindow()
    bus = EventBus()
    bus.subscribe(window.state_changed.emit)
    bus.emit(State.SPEAKING)
    app.processEvents()
    assert window._label.text() == SKINS["playful"][State.SPEAKING]


def test_position_is_saved_and_loaded(tmp_path):
    from PySide6.QtCore import QPoint

    from jarvis.ui.character import load_position, save_position

    path = tmp_path / "character.json"
    assert load_position(path) is None
    save_position(path, QPoint(120, 340))
    assert load_position(path) == QPoint(120, 340)
    path.write_text("not json", encoding="utf-8")
    assert load_position(path) is None


def test_dragging_moves_the_window_and_saves_the_position(tmp_path):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from jarvis.ui.character import CharacterWindow, QApplication, load_position

    QApplication.instance() or QApplication([])
    path = tmp_path / "character.json"
    window = CharacterWindow(path)
    window.move(100, 100)

    def mouse(kind, x, y):
        pos = QPointF(x, y)
        return QMouseEvent(
            kind,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 110, 110))
    window.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 160, 150))
    window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 160, 150))
    assert window.pos() == QPoint(150, 140)
    assert load_position(path) == QPoint(150, 140)


def test_roaming_only_when_idle_and_not_dragged():
    from jarvis.ui.character import CharacterWindow, QApplication

    QApplication.instance() or QApplication([])
    window = CharacterWindow(roam=False)
    window.move(100, 100)
    window.show_state(State.THINKING)
    window.roam_once()
    assert window._glide.state() != window._glide.State.Running
    window.show_state(State.IDLE)
    window.roam_once()
    assert window._glide.state() == window._glide.State.Running
    window.show_state(State.SPEAKING)  # becoming busy stops the glide
    assert window._glide.state() != window._glide.State.Running


def test_click_without_drag_emits_clicked_but_a_drag_does_not(tmp_path):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from jarvis.ui.character import CharacterWindow, QApplication

    QApplication.instance() or QApplication([])
    window = CharacterWindow(tmp_path / "c.json")
    window.move(100, 100)
    clicks = []
    window.clicked.connect(lambda: clicks.append(True))

    def mouse(kind, x, y):
        pos = QPointF(x, y)
        return QMouseEvent(
            kind,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 110, 110))
    window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 110, 110))
    assert clicks == [True]
    assert not (tmp_path / "c.json").exists()  # a click is not a move
    window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 110, 110))
    window.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 150, 150))
    window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 150, 150))
    assert clicks == [True]
