import threading
import time

import pytest
from PySide6.QtWidgets import QApplication

from jarvis.core.assistant import Assistant
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus
from jarvis.core.personality import PersonalityControl
from jarvis.ui.bubble import Bubble
from jarvis.ui.chat import ChatWindow, QtSurface
from jarvis.ui.cli import Reader, make_confirm
from jarvis.ui.confirm import ConfirmDialog, describe
from jarvis.ui.tray import Tray, TrayControls


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def chat(messages, tools=None):
    yield "Hi "
    yield "there"


class FakeVoice:
    wake_available = True

    def __init__(self):
        self.speak_replies = True
        self.wake_enabled = False
        self.stopped = 0

    def stop_speaking(self):
        self.stopped += 1

    def set_wake_word(self, on):
        self.wake_enabled = on
        return on

    def say_async(self, text):
        pass


def build(voice=None):
    reader = Reader(windowed=True)
    surface = QtSurface(reader)
    convo = Conversation(chat, "sys", None, None, help_prompt="HELP")
    assistant = Assistant(convo, None, voice, PersonalityControl("playful"), EventBus())
    submitted = []
    window = ChatWindow(assistant, surface, submitted.append, lambda: submitted.append("QUIT"))
    return reader, surface, assistant, window, submitted


def test_windowed_reader_waits_for_injected_lines_and_close_ends_it():
    reader = Reader(windowed=True)
    reader.inject("hello", "typed")
    assert reader.ask("") == "hello" and reader.last_source == "typed"
    threading.Timer(0.05, reader.close).start()
    with pytest.raises(EOFError):
        reader.ask("")


def test_replies_stream_into_the_transcript(app):
    _, surface, assistant, window, _ = build()
    surface.user_line.emit("hello", "voice")
    assistant.handle("hello", surface)
    app.processEvents()
    text = window.transcript.toPlainText()
    assert "You: hello" in text and "[voice]" in text and "Jarvis: Hi there" in text


def test_notices_and_errors_are_shown(app):
    _, surface, _, window, _ = build()
    surface.notice("Conversation cleared.")
    surface.reply_failed("Cannot reach Ollama")
    app.processEvents()
    text = window.transcript.toPlainText()
    assert "Conversation cleared." in text and "Cannot reach Ollama" in text


def test_every_cli_command_has_a_control(app):
    voice = FakeVoice()
    _, _, assistant, window, submitted = build(voice)
    window.new_chat.click()
    window.forget.click()
    window.help_button.click()  # /stuck
    assert submitted == ["/clear", "/forget", "/stuck"]
    assistant.conversation.set_help_mode(True)
    window.help_button.click()
    assert submitted[-1] == "/stuck off"
    window.stop.click()
    assert voice.stopped == 1
    window.speak.setChecked(False)
    assert voice.speak_replies is False and voice.stopped == 2
    window.wake.setChecked(True)
    assert voice.wake_enabled is True
    window.personality.activated.emit(1)
    assert assistant.personality.value == "formal"
    window.input.setText("what time is it")
    window.input.returnPressed.emit()
    assert submitted[-1] == "what time is it" and window.input.text() == ""


def test_controls_follow_outside_changes_and_work_without_voice(app):
    voice = FakeVoice()
    _, _, assistant, window, _ = build(voice)
    voice.speak_replies = False  # e.g. /speak off typed in the box
    assistant.personality.set("formal")
    app.processEvents()
    assert not window.speak.isChecked() and window.personality.currentIndex() == 1
    _, _, _, bare, _ = build(None)
    assert not bare.speak.isEnabled() and not bare.wake.isEnabled() and not bare.stop.isEnabled()


def run_on_worker(app, fn, act, timeout=5.0):
    """Run `fn` on a worker thread (like the chat loop) while this thread runs Qt events and
    calls `act()` once the worker is waiting. Returns fn's result."""
    result = []
    worker = threading.Thread(target=lambda: result.append(fn()), daemon=True)
    worker.start()
    deadline = time.monotonic() + timeout
    acted = False
    while worker.is_alive() and time.monotonic() < deadline:
        app.processEvents()
        if not acted and time.monotonic() > deadline - timeout + 0.1:
            act()
            acted = True
        time.sleep(0.01)
    worker.join(1)
    assert result, "the worker never finished"
    return result[0]


def test_confirm_dialog_buttons_answer_through_the_reader(app):
    reader = Reader(windowed=True)
    surface = QtSurface(reader)
    dialog = ConfirmDialog(lambda yes: reader.inject("yes" if yes else "no", "popup"))
    surface.question_asked.connect(dialog.ask)
    surface.question_closed.connect(dialog.hide)
    shown = []
    confirm = make_confirm(
        reader,
        None,
        show=lambda name, args: surface.question_asked.emit(describe(name, args)),
        hide=surface.question_closed.emit,
    )
    surface.question_asked.connect(shown.append)
    assert run_on_worker(app, lambda: confirm("close_app", {"name": "notepad"}), dialog.yes.click)
    assert shown == ["close app: name = notepad"]
    assert not run_on_worker(app, lambda: confirm("close_app", {}), dialog.no.click)
    app.processEvents()
    assert not dialog.isVisible()


def test_a_spoken_no_also_answers_and_closes_the_dialog(app):
    reader = Reader(windowed=True)
    surface = QtSurface(reader)
    dialog = ConfirmDialog(lambda yes: None)
    surface.question_asked.connect(dialog.ask)
    surface.question_closed.connect(dialog.hide)
    confirm = make_confirm(
        reader,
        None,
        show=lambda n, a: surface.question_asked.emit("Run?"),
        hide=surface.question_closed.emit,
    )
    result = run_on_worker(
        app, lambda: confirm("delete_file", {"path": "x"}), lambda: reader.inject("no thanks")
    )
    app.processEvents()
    assert result is False and not dialog.isVisible()


def test_forget_question_goes_to_the_popup_and_back(app):
    reader = Reader(windowed=True)
    surface = QtSurface(reader)
    questions = []
    surface.question_asked.connect(questions.append)
    answered = run_on_worker(
        app, lambda: surface.ask_yes_no("Wipe everything?"), lambda: reader.inject("yes", "popup")
    )
    app.processEvents()
    assert answered is True and questions == ["Wipe everything?"]


def test_alert_bubble_shows_the_message(app):
    from jarvis.ui.character import CharacterWindow

    window = CharacterWindow()
    window.show()
    bubble = Bubble(seconds=5)
    bubble.attach(window)
    bubble.message_ready.emit("Reminder: stretch")
    app.processEvents()
    assert bubble.isVisible() and bubble.label.text() == "Reminder: stretch"
    bubble.mousePressEvent(None)
    assert not bubble.isVisible()
    window.hide()


def test_tray_has_open_chat_and_wake_controls(app):
    from jarvis.ui.character import CharacterWindow

    opened = []
    wake = {"on": False}

    def set_wake(on):
        wake["on"] = on
        return on

    controls = TrayControls(
        on_open_chat=lambda: opened.append(1), is_wake_on=lambda: wake["on"], set_wake=set_wake
    )
    tray = Tray(app, CharacterWindow(), controls)
    tray.open_chat.trigger()
    assert opened == [1]
    tray.wake.setChecked(True)
    assert wake["on"] is True
    wake["on"] = False
    tray._sync()
    assert not tray.wake.isChecked()
