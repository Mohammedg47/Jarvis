"""The chat window: the Qt main interface. Every terminal command has a control here."""

import html
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from jarvis.core.assistant import Assistant, is_yes
from jarvis.core.personality import PERSONALITIES
from jarvis.ui.cli import Reader


class QtSurface(QObject):
    """The assistant's `Surface` for Qt. It is called from the chat thread, so everything goes
    out as signals that the windows receive on the Qt thread."""

    user_line = Signal(str, str)  # text, source (typed, voice, overlay...)
    notice_shown = Signal(str)
    reply_begun = Signal()
    reply_text = Signal(str)
    reply_done = Signal(str)
    reply_error = Signal(str)
    reply_stopped = Signal()
    question_asked = Signal(str)  # a yes/no question for the confirm popup
    question_closed = Signal()

    def __init__(self, reader: Reader) -> None:
        super().__init__()
        self._reader = reader

    def notice(self, text: str) -> None:
        self.notice_shown.emit(text)

    def reply_started(self) -> None:
        self.reply_begun.emit()

    def reply_chunk(self, text: str) -> None:
        self.reply_text.emit(text)

    def reply_finished(self, text: str) -> None:
        self.reply_done.emit(text)

    def reply_failed(self, text: str) -> None:
        self.reply_error.emit(text)

    def reply_interrupted(self) -> None:
        self.reply_stopped.emit()

    def ask_yes_no(self, question: str) -> bool:
        self.question_asked.emit(question)
        try:
            return is_yes(self._reader.ask(f"{question} [y/N] ", fresh=True))
        finally:
            self.question_closed.emit()


class ChatWindow(QWidget):
    """Transcript, input line and a control for each slash command."""

    refresh_signal = Signal()  # personality changes can come from any thread

    def __init__(
        self,
        assistant: Assistant,
        surface: QtSurface,
        submit: Callable[[str], None],
        quit_app: Callable[[], None],
    ) -> None:
        super().__init__()
        self._assistant = assistant
        self._submit = submit
        self.setWindowTitle("Jarvis")
        self.resize(460, 560)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(True)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask Jarvis, or type /help for commands...")
        self.input.returnPressed.connect(self._send)
        send = QPushButton("Send")
        send.clicked.connect(self._send)

        # One control per CLI command: /clear /forget /speak /stop /wake /personality /stuck /exit.
        self.new_chat = QPushButton("New chat")
        self.new_chat.setToolTip("/clear - start a fresh conversation (saved memory is kept)")
        self.new_chat.clicked.connect(lambda: submit("/clear"))
        self.forget = QPushButton("Forget everything")
        self.forget.setToolTip("/forget - wipe all saved history and preferences")
        self.forget.clicked.connect(lambda: submit("/forget"))
        self.stop = QPushButton("Stop talking")
        self.stop.setToolTip("/stop - cut off the spoken reply (or press Esc)")
        self.stop.clicked.connect(self._stop_speaking)
        self.speak = QCheckBox("Spoken replies")
        self.speak.setToolTip("/speak")
        self.speak.toggled.connect(self._set_speak)
        self.wake = QCheckBox('"Hey Jarvis"')
        self.wake.setToolTip("/wake - hands-free listening")
        self.wake.toggled.connect(self._set_wake)
        self.personality = QComboBox()
        self.personality.setToolTip("/personality")
        self.personality.addItems([name.capitalize() for name in PERSONALITIES])
        self.personality.activated.connect(lambda i: assistant.personality.set(PERSONALITIES[i]))
        self.help_button = QPushButton("I need help")
        self.help_button.setCheckable(True)
        self.help_button.setToolTip("/stuck - step-by-step help mode (it can look at your screen)")
        self.help_button.clicked.connect(self._toggle_help)
        commands = QPushButton("Commands")
        commands.setToolTip("/help - list the typed commands")
        commands.clicked.connect(lambda: submit("/help"))
        quit_button = QPushButton("Quit")
        quit_button.setToolTip("/exit")
        quit_button.clicked.connect(quit_app)

        top = QHBoxLayout()
        for widget in (self.new_chat, self.forget, self.stop, commands, quit_button):
            top.addWidget(widget)
        options = QHBoxLayout()
        for widget in (self.speak, self.wake, self.personality, self.help_button):
            options.addWidget(widget)
        options.addStretch()
        bottom = QHBoxLayout()
        bottom.addWidget(self.input)
        bottom.addWidget(send)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(options)
        layout.addWidget(self.transcript)
        layout.addLayout(bottom)

        surface.user_line.connect(self.add_user)
        surface.notice_shown.connect(self.add_notice)
        surface.reply_begun.connect(self.begin_reply)
        surface.reply_text.connect(self.add_reply_text)
        surface.reply_done.connect(self.end_reply)
        surface.reply_error.connect(self.add_error)
        surface.reply_stopped.connect(lambda: self.add_notice("[interrupted]"))
        assistant.personality.subscribe(lambda _: self.refresh_signal.emit())
        self.refresh_signal.connect(self.refresh)
        self.refresh()

    # -- transcript ---------------------------------------------------------------------------

    def _append_html(self, markup: str) -> None:
        self.transcript.append(markup)

    def add_user(self, text: str, source: str) -> None:
        tag = (
            ""
            if source == "typed"
            else f" <span style='color:#9aa0a6'>[{html.escape(source)}]</span>"
        )
        self._append_html(f"<p><b style='color:#1a73e8'>You:</b> {html.escape(text)}{tag}</p>")

    def add_notice(self, text: str) -> None:
        self._append_html(f"<p style='color:#80868b'><i>{html.escape(text)}</i></p>")
        self.refresh()

    def add_error(self, text: str) -> None:
        self._append_html(f"<p style='color:#d93025'>{html.escape(text)}</p>")

    def begin_reply(self) -> None:
        self.transcript.append("<p><b style='color:#188038'>Jarvis:</b> </p>")

    def add_reply_text(self, text: str) -> None:
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def end_reply(self, text: str) -> None:
        self.refresh()

    # -- controls -----------------------------------------------------------------------------

    def _send(self) -> None:
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self._submit(text)

    def _voice(self):
        return self._assistant.voice

    def _stop_speaking(self) -> None:
        if self._voice() is not None:
            self._voice().stop_speaking()

    def _set_speak(self, on: bool) -> None:
        voice = self._voice()
        if voice is not None and voice.speak_replies != on:
            voice.speak_replies = on
            if not on:
                voice.stop_speaking()

    def _set_wake(self, on: bool) -> None:
        voice = self._voice()
        if voice is not None and voice.wake_enabled != on:
            actual = voice.set_wake_word(on)
            if actual != on:  # it could not start; show the real state
                self.wake.blockSignals(True)
                self.wake.setChecked(actual)
                self.wake.blockSignals(False)

    def _toggle_help(self) -> None:
        self._submit("/stuck" if not self._assistant.conversation.help_mode else "/stuck off")

    def refresh(self) -> None:
        """Bring every control in line with the real state (a command may have changed it)."""
        voice = self._voice()
        for box, enabled, value in (
            (self.speak, voice is not None, bool(voice and voice.speak_replies)),
            (self.wake, bool(voice and voice.wake_available), bool(voice and voice.wake_enabled)),
        ):
            box.blockSignals(True)
            box.setEnabled(enabled)
            box.setChecked(value)
            box.blockSignals(False)
        self.stop.setEnabled(voice is not None)
        self.personality.blockSignals(True)
        self.personality.setCurrentIndex(PERSONALITIES.index(self._assistant.personality.value))
        self.personality.blockSignals(False)
        self.help_button.blockSignals(True)
        self.help_button.setChecked(self._assistant.conversation.help_mode)
        self.help_button.blockSignals(False)

    def open_window(self) -> None:
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
