"""Runs Jarvis as a Qt app: the main interface (no terminal needed).

Qt owns the main thread. The assistant loop runs on a worker thread that waits for lines (typed
in a window, spoken, or sent by a hotkey) and shows results through signals. The terminal
interface (`python -m jarvis --cli`) stays as the debug/secondary mode.
"""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from jarvis.core.assistant import Assistant
from jarvis.core.events import EventBus, Notifier
from jarvis.ui import face
from jarvis.ui.bubble import Bubble
from jarvis.ui.character import CharacterWindow
from jarvis.ui.chat import ChatWindow, QtSurface
from jarvis.ui.cli import Reader
from jarvis.ui.confirm import ConfirmDialog
from jarvis.ui.popup import InputPopup
from jarvis.ui.tray import Tray, TrayControls
from jarvis.voice.hotkey import PressHotkey

logger = logging.getLogger("jarvis.ui")


class _Signals(QObject):
    """Thread hops: hotkeys and the chat thread ask the Qt thread to do things."""

    finished = Signal()  # the chat loop ended (the user said /exit)
    help_requested = Signal()


def _answer_dialog(reader: Reader):
    """The Yes/No popup's buttons answer through the reader, like typing or saying "yes"."""
    return lambda yes: reader.inject("yes" if yes else "no", "popup")


def run_app(
    assistant: Assistant,
    reader: Reader,
    surface: QtSurface,
    bus: EventBus,
    notifier: Notifier,
    controls: TrayControls,
    position_file: Path | None = None,
    roam: bool = False,
    help_hotkey: str = "",
    show_character: bool = True,
    open_chat: bool = True,
    character_style: str = "noto",
) -> None:
    """Show the character, tray and chat window and run the assistant loop on a worker thread.
    Returns when the user quits (tray, chat window or /exit)."""
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)  # the tray's Quit ends the app
    face.set_style(character_style)
    personality = assistant.personality
    window = CharacterWindow(position_file, roam, personality.value)
    window.place()

    chat = ChatWindow(assistant, surface, lambda text: reader.inject(text, "typed"), app.quit)
    popup = InputPopup(lambda text: reader.inject(text, "overlay"))
    popup.expand_requested.connect(chat.open_window)
    window.clicked.connect(lambda: popup.open_near(window))
    surface.reply_done.connect(popup.show_reply)
    surface.notice_shown.connect(popup.show_reply)
    surface.reply_error.connect(lambda text: popup.show_reply(f"[error] {text}"))

    confirm = ConfirmDialog(_answer_dialog(reader))
    surface.question_asked.connect(confirm.ask)
    surface.question_closed.connect(confirm.hide)

    bubble = Bubble()
    bubble.attach(window)
    notifier.subscribe(bubble.message_ready.emit)

    signals = _Signals()

    def start_help() -> None:
        chat.open_window()
        reader.inject("/stuck", "help")

    signals.help_requested.connect(start_help)
    controls.on_help = signals.help_requested.emit
    controls.on_open_chat = chat.open_window
    help_key = None
    if help_hotkey:
        try:
            help_key = PressHotkey(help_hotkey, signals.help_requested.emit)
            help_key.start()
        except Exception:
            logger.exception("Could not install the help hotkey")
            help_key = None

    tray = Tray(app, window, controls)
    if not tray.show():
        logger.warning("No system tray is available; Quit and Mute are not on offer.")
    personality.subscribe(window.personality_changed.emit)
    bus.subscribe(window.state_changed.emit)
    window.show_state(bus.state)
    if show_character:
        window.show()
    if open_chat or not show_character:  # without the character there is nothing else to click
        chat.open_window()

    signals.finished.connect(app.quit)

    def work() -> None:
        try:
            while True:
                try:
                    text = reader.ask("")
                except (EOFError, KeyboardInterrupt):
                    break
                surface.user_line.emit(text, reader.last_source)
                if not assistant.handle(text, surface):
                    break
        finally:
            signals.finished.emit()

    threading.Thread(target=work, name="jarvis-chat", daemon=True).start()
    app.exec()
    reader.close()
    if help_key is not None:
        help_key.stop()
