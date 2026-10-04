"""Terminal chat interface (the debug / secondary interface; the Qt app is the main one)."""

import queue
import sys
import threading
from collections.abc import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from jarvis.core.assistant import HELP, Assistant, is_yes
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus
from jarvis.core.personality import PersonalityControl
from jarvis.memory import MemoryStore
from jarvis.voice.session import VoiceSession

__all__ = ["HELP", "Reader", "TerminalSurface", "is_yes", "make_confirm", "run_cli"]


class Reader:
    """The single input source: lines typed in the terminal, plus text injected from other
    threads (voice transcripts, the chat window, hotkeys), returned as if typed.

    A windowed app (`windowed=True`) never touches the terminal: `ask` just waits for injected
    lines. `inject` interrupts a terminal prompt that is waiting.
    """

    def __init__(self, windowed: bool = False) -> None:
        self._windowed = windowed
        self.interactive = not windowed and bool(sys.stdin and sys.stdin.isatty())
        # prompt_toolkit needs a real console; piped stdin falls back to input().
        self._session = PromptSession() if self.interactive else None
        self._voice_lines: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self._lock = threading.Lock()
        self._waiting = False
        self.last_source = "typed"  # where the line `ask` last returned came from

    def inject(self, text: str, source: str = "voice") -> None:
        """Hand a voice transcript (or text typed in a window) to the active or next prompt.
        Safe from any thread."""
        with self._lock:
            self._voice_lines.put((text, source))
            if self._waiting and self._session is not None:
                app = self._session.app
                if app.is_running:
                    app.loop.call_soon_threadsafe(lambda: app.exit(result=""))

    def close(self) -> None:
        """Wake a waiting `ask` for good: it raises EOFError (a windowed app is shutting down)."""
        self._voice_lines.put(None)

    def _take_voice(self, label: str) -> str | None:
        try:
            item = self._voice_lines.get_nowait()
        except queue.Empty:
            return None
        if item is None:
            raise EOFError
        text, source = item
        self.last_source = source
        if self.interactive:
            print(f"{label}{text}  [{source}]")
        return text

    def ask(self, label: str, fresh: bool = False) -> str:
        """Prompt for a line. `fresh` drops input injected before this question."""
        if fresh:
            while not self._voice_lines.empty():
                self._voice_lines.get_nowait()
        self.last_source = "typed"
        voice = self._take_voice(label)
        if voice is not None:
            return voice
        if self._session is None:
            if not self._windowed:
                return input(label)  # piped stdin (scripts, tests)
            item = self._voice_lines.get()  # a windowed app: only injected lines arrive
            if item is None:
                raise EOFError
            self.last_source = item[1]
            return item[0]
        with self._lock:
            self._waiting = True
        try:
            with patch_stdout():  # reminders can print while the prompt is waiting
                typed = self._session.prompt(label)
        finally:
            with self._lock:
                self._waiting = False
        voice = self._take_voice(label)
        return typed if voice is None else voice


def make_confirm(
    reader: Reader,
    voice: VoiceSession | None = None,
    show: Callable[[str, dict], None] | None = None,
    hide: Callable[[], None] | None = None,
) -> Callable[[str, dict], bool]:
    """Confirmation callback for risky tools: answer by typing or by voice. A windowed app
    passes `show`/`hide` for its Yes/No popup, whose buttons inject "yes"/"no" into the reader."""

    def confirm(name: str, arguments: dict) -> bool:
        args = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        print(f"\n[confirm] Jarvis wants to run {name}({args}).")
        if show is not None:
            show(name, arguments)
        if voice is not None and voice.speak_replies:
            voice.say(f"Should I run {name.replace('_', ' ')}? Say yes or no.")
        try:
            return is_yes(reader.ask("Allow? [y/N] ", fresh=True))
        finally:
            if hide is not None:
                hide()

    return confirm


class TerminalSurface:
    """Shows the assistant's output in the terminal (and in the overlay via `on_reply`)."""

    def __init__(self, reader: Reader, on_reply: Callable[[str], None] | None = None) -> None:
        self._reader = reader
        self._on_reply = on_reply

    def _show(self, text: str) -> None:  # the overlay shows replies too
        if self._on_reply is not None:
            self._on_reply(text)

    def notice(self, text: str) -> None:
        print(text)
        self._show(text)

    def reply_started(self) -> None:
        print("Jarvis: ", end="", flush=True)

    def reply_chunk(self, text: str) -> None:
        print(text, end="", flush=True)

    def reply_finished(self, text: str) -> None:
        print()
        self._show(text)

    def reply_failed(self, text: str) -> None:
        print(f"\n[error] {text}")
        self._show(f"[error] {text}")

    def reply_interrupted(self) -> None:
        print("\n[interrupted]")

    def ask_yes_no(self, question: str) -> bool:
        return is_yes(self._reader.ask(f"{question} [y/N] "))


def run_cli(
    conversation: Conversation,
    memory: MemoryStore | None = None,
    reader: Reader | None = None,
    voice: VoiceSession | None = None,
    personality: PersonalityControl | None = None,
    bus: EventBus | None = None,
    on_reply: Callable[[str], None] | None = None,
) -> None:
    reader = reader or Reader()
    assistant = Assistant(conversation, memory, voice, personality, bus)
    surface = TerminalSurface(reader, on_reply)
    print(f"Jarvis is ready. {HELP}")
    if voice is not None:
        print("Hold the push-to-talk hotkey to speak.")
    while True:
        try:
            text = reader.ask("You: ")
        except (EOFError, KeyboardInterrupt):
            break
        if not assistant.handle(text, surface):
            break
    print("Goodbye.")
