"""Terminal chat interface."""

import queue
import re
import sys
import threading
from collections.abc import Callable

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, State
from jarvis.core.personality import PERSONALITIES, PersonalityControl
from jarvis.llm.client import LLMError
from jarvis.memory import MemoryStore
from jarvis.voice.session import VoiceSession

HELP = (
    "Commands: /clear  reset this conversation, /forget  wipe all saved memory, "
    "/speak [on|off]  toggle spoken replies, /stop  stop talking (or press Esc), /personality [playful|formal]  change tone "
    "(no argument switches), /help  show this, /exit  quit"
)

YES_WORDS = {"y", "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "proceed"}


def is_yes(answer: str) -> bool:
    """True for an explicit yes, typed or transcribed ("Yes." counts). Anything else is no."""
    words = re.sub(r"[^\w\s]", "", answer).lower().split()
    return bool(words) and words[0] in YES_WORDS


class Reader:
    """Reads lines from the keyboard. Voice transcripts can be injected from another thread
    and are returned as if typed, interrupting the prompt that is waiting."""

    def __init__(self) -> None:
        self.interactive = sys.stdin.isatty()
        # prompt_toolkit needs a real console; piped stdin falls back to input().
        self._session = PromptSession() if self.interactive else None
        self._voice_lines: queue.Queue[tuple[str, str]] = queue.Queue()
        self._lock = threading.Lock()
        self._waiting = False

    def inject(self, text: str, source: str = "voice") -> None:
        """Hand a voice transcript (or text typed in the overlay) to the active or next
        prompt. Safe from any thread."""
        with self._lock:
            self._voice_lines.put((text, source))
            if self._waiting and self._session is not None:
                app = self._session.app
                if app.is_running:
                    app.loop.call_soon_threadsafe(lambda: app.exit(result=""))

    def _take_voice(self, label: str) -> str | None:
        try:
            text, source = self._voice_lines.get_nowait()
        except queue.Empty:
            return None
        print(f"{label}{text}  [{source}]")
        return text

    def ask(self, label: str, fresh: bool = False) -> str:
        """Prompt for a line. `fresh` drops voice input spoken before this question."""
        if fresh:
            while not self._voice_lines.empty():
                self._voice_lines.get_nowait()
        voice = self._take_voice(label)
        if voice is not None:
            return voice
        if self._session is None:
            return input(label)
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


def make_confirm(reader: Reader, voice: VoiceSession | None = None) -> Callable[[str, dict], bool]:
    """Confirmation callback for risky tools: answer by typing or by voice."""

    def confirm(name: str, arguments: dict) -> bool:
        args = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
        print(f"\n[confirm] Jarvis wants to run {name}({args}).")
        if voice is not None and voice.speak_replies:
            voice.say(f"Should I run {name.replace('_', ' ')}? Say yes or no.")
        return is_yes(reader.ask("Allow? [y/N] ", fresh=True))

    return confirm


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
    bus = bus or EventBus()
    personality = personality or PersonalityControl()

    def show(text: str) -> None:  # the overlay shows replies too
        if on_reply is not None:
            on_reply(text)

    print(f"Jarvis is ready. {HELP}")
    if voice is not None:
        print("Hold the push-to-talk hotkey to speak.")
    while True:
        try:
            text = reader.ask("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if voice is not None:
            voice.stop_speaking()  # a new message cuts off the previous reply
        if text.startswith("/"):
            command, _, arg = text.lower().partition(" ")
            if command in ("/exit", "/quit"):
                break
            if command == "/clear":
                conversation.clear()
                print("Conversation cleared.")
            elif command == "/forget":
                if memory is None:
                    print("There is no saved memory.")
                elif is_yes(reader.ask("Wipe all saved history and preferences? [y/N] ")):
                    memory.forget_all()
                    conversation.clear()
                    print("Memory wiped.")
                else:
                    print("Memory kept.")
            elif command == "/stop":
                pass  # speech was already stopped above
            elif command == "/speak":
                if voice is None:
                    print("Voice is not available (set ELEVENLABS_API_KEY and use a console).")
                else:
                    voice.speak_replies = {"on": True, "off": False}.get(
                        arg.strip(), not voice.speak_replies
                    )
                    print(f"Spoken replies are {'on' if voice.speak_replies else 'off'}.")
            elif command == "/personality":
                if arg.strip() in PERSONALITIES:
                    personality.set(arg.strip())
                else:
                    personality.toggle()
                print(f"Personality is now {personality.value}.")
            elif command == "/help":
                print(HELP)
            else:
                print(f"Unknown command {text}. {HELP}")
            continue

        print("Jarvis: ", end="", flush=True)
        reply: list[str] = []
        speaking = False  # the speech thread then reports the return to idle
        bus.emit(State.THINKING)
        try:
            for chunk in conversation.send(text):
                reply.append(chunk)
                print(chunk, end="", flush=True)
        except LLMError as exc:
            print(f"\n[error] {exc}")
            show(f"[error] {exc}")
        except KeyboardInterrupt:
            print("\n[interrupted]")
        else:
            print()
            show("".join(reply))
            if voice is not None and voice.speak_replies:
                speaking = True
                voice.say_async("".join(reply))  # the prompt stays free to type, talk or stop
        finally:
            if not speaking:
                bus.emit(State.IDLE)
    print("Goodbye.")
