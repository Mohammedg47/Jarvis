"""Runs Jarvis with the floating character.

Qt must own the main thread, so `run_character` runs the rest of Jarvis (the terminal chat
loop) on a worker thread and returns when either side finishes (or the tray's Quit is used).
"""

import threading
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from jarvis.core.events import EventBus
from jarvis.ui.character import CharacterWindow, logger
from jarvis.ui.popup import InputPopup
from jarvis.ui.tray import Tray, TrayControls


class _Done(QObject):
    """Lets the worker thread ask the Qt thread to quit (signals queue across threads)."""

    finished = Signal()


def run_character(
    worker: Callable[[Callable[[str], None]], None],
    submit: Callable[[str], None] | None = None,
    bus: EventBus | None = None,
    position_file: Path | None = None,
    roam: bool = False,
    controls: TrayControls | None = None,
) -> None:
    """Show the character and run `worker` on a thread; return when the worker ends or Quit
    is chosen. `worker` gets a thread-safe `show_reply(text)` for the overlay; clicking the
    character opens a text box whose lines go to `submit`."""
    app = QApplication.instance() or QApplication([])
    window = CharacterWindow(
        position_file,
        roam,
        controls.personality.value if controls and controls.personality else "playful",
    )
    window.place()
    show_reply: Callable[[str], None] = lambda text: None
    if submit is not None:
        popup = InputPopup(submit)
        window.clicked.connect(lambda: popup.open_near(window))
        show_reply = popup.reply_ready.emit
    window.show()
    app.setQuitOnLastWindowClosed(False)  # the tray's Quit ends the app
    tray = Tray(app, window, controls or TrayControls())
    if not tray.show():
        logger.warning("No system tray is available; Quit and Mute are not on offer.")
    if controls is not None and controls.personality is not None:
        controls.personality.subscribe(window.personality_changed.emit)
    if bus is not None:
        bus.subscribe(window.state_changed.emit)
        window.show_state(bus.state)

    done = _Done()
    done.finished.connect(app.quit)

    def work() -> None:
        try:
            worker(show_reply)
        finally:
            done.finished.emit()

    threading.Thread(target=work, name="jarvis-cli", daemon=True).start()
    app.exec()
