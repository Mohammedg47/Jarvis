from jarvis.ui.character import QApplication
from jarvis.ui.popup import THINKING_TEXT, InputPopup


def make(submit):
    app = QApplication.instance() or QApplication([])
    return app, InputPopup(submit)


def test_enter_submits_the_text_and_shows_a_waiting_mark():
    sent = []
    _, popup = make(sent.append)
    popup.input.setText("  open notepad ")
    popup.input.returnPressed.emit()
    assert sent == ["open notepad"]
    assert popup.input.text() == ""
    assert popup.reply.text() == THINKING_TEXT


def test_empty_input_is_ignored_and_replies_are_shown():
    sent = []
    app, popup = make(sent.append)
    popup.input.returnPressed.emit()
    assert sent == []
    popup.reply_ready.emit("It is 3 pm.")
    app.processEvents()
    assert popup.reply.text() == "It is 3 pm."


def _mouse(kind, x, y):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    pos = QPointF(x, y)
    return QMouseEvent(
        kind,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_x_button_closes_the_popup():
    _, popup = make(lambda text: None)
    popup.show()
    assert popup.isVisible()
    popup.close_button.click()
    assert not popup.isVisible()


def test_dragging_moves_the_popup_and_reopens_where_it_was_left():
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtWidgets import QWidget

    _, popup = make(lambda text: None)
    popup.move(200, 200)
    popup.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 210, 210))
    popup.mouseMoveEvent(_mouse(QEvent.Type.MouseMove, 260, 250))
    popup.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 260, 250))
    assert popup.pos() == QPoint(250, 240)
    popup.hide()
    popup.open_near(QWidget())  # would normally be placed by the anchor
    assert popup.pos() == QPoint(250, 240)


def test_a_plain_click_does_not_pin_the_position():
    from PySide6.QtCore import QEvent

    _, popup = make(lambda text: None)
    popup.mousePressEvent(_mouse(QEvent.Type.MouseButtonPress, 10, 10))
    popup.mouseReleaseEvent(_mouse(QEvent.Type.MouseButtonRelease, 10, 10))
    assert popup._moved_to is None
