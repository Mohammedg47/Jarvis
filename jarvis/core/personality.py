"""The current personality (Playful or Formal), shared by the CLI, the tray and the character."""

import threading
from collections.abc import Callable

PERSONALITIES = ("playful", "formal")


class PersonalityControl:
    """Holds the personality and tells subscribers when it changes. Safe from any thread;
    subscribers run on the thread that changed it."""

    def __init__(self, value: str = "playful") -> None:
        self.value = value if value in PERSONALITIES else "playful"
        self._subscribers: list[Callable[[str], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def set(self, value: str) -> None:
        if value not in PERSONALITIES:
            raise ValueError(f"Unknown personality {value!r}")
        with self._lock:
            if value == self.value:
                return
            self.value = value
            subscribers = list(self._subscribers)
        for callback in subscribers:
            callback(value)

    def toggle(self) -> str:
        self.set("formal" if self.value == "playful" else "playful")
        return self.value
