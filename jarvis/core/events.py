"""Event bus: the core announces what Jarvis is doing; the CLI and the character listen."""

import logging
import threading
from collections.abc import Callable
from enum import Enum

logger = logging.getLogger("jarvis.events")


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class EventBus:
    """Publishes state changes to subscribers. Safe to emit from any thread.

    Subscribers run on the emitting thread, so they must be quick and must not raise
    (a failing one is logged and skipped). Repeating the current state is not an event.
    """

    def __init__(self) -> None:
        self.state = State.IDLE
        self._subscribers: list[Callable[[State], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[State], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def emit(self, state: State) -> None:
        with self._lock:
            if state == self.state:
                return
            self.state = state
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(state)
            except Exception:
                logger.exception("Event subscriber failed")


def log_state(state: State) -> None:
    """Subscriber that logs every state change (shown in the CLI and the log file)."""
    logger.info("state: %s", state.value)


class Notifier:
    """Broadcasts alert messages (reminders, calendar and email alerts) to every interface.

    Subscribers run on the thread that raised the alert, so a Qt subscriber must hand the text
    to the Qt thread through a signal.
    """

    def __init__(self) -> None:
        self._subscribers: list[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def notify(self, message: str) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(message)
            except Exception:
                logger.exception("Alert subscriber failed")
