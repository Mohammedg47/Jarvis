"""Push-to-talk: hold the hotkey to record, release to send."""

from collections.abc import Callable

import keyboard


class HoldTracker:
    """Turns raw key events into start/stop calls for a held key combination."""

    def __init__(self, hotkey: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        self._keys = {part.strip().lower() for part in hotkey.split("+") if part.strip()}
        self._down: set[str] = set()
        self._active = False
        self._on_start = on_start
        self._on_stop = on_stop

    def key_event(self, name: str | None, pressed: bool) -> None:
        name = (name or "").lower()
        if name not in self._keys:
            return
        if pressed:
            self._down.add(name)
            if not self._active and self._down == self._keys:
                self._active = True
                self._on_start()
        else:
            self._down.discard(name)
            if self._active:
                self._active = False
                self._on_stop()


class PressHotkey:
    """Global single-press hotkey (works while other apps have focus; the key still reaches them)."""

    def __init__(self, hotkey: str, on_press: Callable[[], None]):
        self._hotkey = hotkey
        self._on_press = on_press
        self._handle = None

    def start(self) -> None:
        self._handle = keyboard.add_hotkey(self._hotkey, self._on_press)

    def stop(self) -> None:
        if self._handle is not None:
            keyboard.remove_hotkey(self._handle)
            self._handle = None


class PushToTalk:
    """Global hold-to-talk hotkey (works while other apps have focus)."""

    def __init__(self, hotkey: str, on_start: Callable[[], None], on_stop: Callable[[], None]):
        self._tracker = HoldTracker(hotkey, on_start, on_stop)
        self._hook = None

    def start(self) -> None:
        self._hook = keyboard.hook(
            lambda e: self._tracker.key_event(e.name, e.event_type == keyboard.KEY_DOWN)
        )

    def stop(self) -> None:
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
