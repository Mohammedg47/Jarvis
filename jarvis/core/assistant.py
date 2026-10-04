"""The chat logic shared by every interface: slash commands and the reply loop.

The terminal and the Qt window both feed lines to `Assistant.handle` and show what happens
through a `Surface`, so a command works the same everywhere.
"""

import re
from typing import Protocol

from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, State
from jarvis.core.personality import PERSONALITIES, PersonalityControl
from jarvis.llm.client import LLMError
from jarvis.memory import MemoryStore
from jarvis.voice.session import VoiceSession

HELP = (
    "Commands: /clear  reset this conversation, /forget  wipe all saved memory, "
    "/speak [on|off]  toggle spoken replies, /stop  stop talking (or press Esc), "
    "/wake [on|off]  hands-free listening, /personality [playful|formal]  change tone "
    "(no argument switches), /stuck [topic|off]  step-by-step help mode, /help  show this, "
    "/exit  quit"
)

YES_WORDS = {"y", "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "proceed"}
NO_VOICE = "Voice is not available (set ELEVENLABS_API_KEY in .env)."


def is_yes(answer: str) -> bool:
    """True for an explicit yes, typed or transcribed ("Yes." counts). Anything else is no."""
    words = re.sub(r"[^\w\s]", "", answer).lower().split()
    return bool(words) and words[0] in YES_WORDS


class Surface(Protocol):
    """Where the assistant shows things. The terminal and the Qt window each implement it."""

    def notice(self, text: str) -> None:
        """A message from Jarvis itself (a command's result, not a model reply)."""

    def reply_started(self) -> None: ...

    def reply_chunk(self, text: str) -> None: ...

    def reply_finished(self, text: str) -> None:
        """The reply is complete; `text` is all of it."""

    def reply_failed(self, text: str) -> None:
        """The model could not answer (Ollama down, model missing...)."""

    def reply_interrupted(self) -> None: ...

    def ask_yes_no(self, question: str) -> bool: ...


class Assistant:
    def __init__(
        self,
        conversation: Conversation,
        memory: MemoryStore | None = None,
        voice: VoiceSession | None = None,
        personality: PersonalityControl | None = None,
        bus: EventBus | None = None,
    ) -> None:
        self.conversation = conversation
        self.memory = memory
        self.voice = voice
        self.personality = personality or PersonalityControl()
        self.bus = bus or EventBus()

    def handle(self, text: str, surface: Surface) -> bool:
        """Handle one line from the user. Returns False when the user asked to quit."""
        text = text.strip()
        if not text:
            return True
        if self.voice is not None:
            self.voice.stop_speaking()  # a new message cuts off the previous reply
        if text.lower().startswith("/stuck"):
            _, _, topic = text.partition(" ")
            topic = self._stuck(topic.strip(), surface)
            if not topic:
                return True
            text = topic  # help mode is on; send the topic as the first message
        elif text.startswith("/"):
            return self._command(text, surface)
        self._reply(text, surface)
        return True

    def _stuck(self, topic: str, surface: Surface) -> str:
        """Handle /stuck. Returns the topic to send as a message, or "" if nothing to send."""
        if topic.lower() in ("off", "stop", "done"):
            self.conversation.set_help_mode(False)
            surface.notice("Help mode is off.")
            return ""
        self.conversation.set_help_mode(True)
        if topic:
            return topic
        surface.notice("Help mode is on. What are you stuck on? (/stuck off to leave it.)")
        if self.voice is not None and self.voice.speak_replies:
            self.voice.say_async("What are you stuck on?")
        return ""

    def _command(self, text: str, surface: Surface) -> bool:
        command, _, arg = text.lower().partition(" ")
        arg = arg.strip()
        voice = self.voice
        if command in ("/exit", "/quit"):
            return False
        if command == "/clear":
            self.conversation.clear()
            surface.notice("Conversation cleared.")
        elif command == "/forget":
            if self.memory is None:
                surface.notice("There is no saved memory.")
            elif surface.ask_yes_no("Wipe all saved history and preferences?"):
                self.memory.forget_all()
                self.conversation.clear()
                surface.notice("Memory wiped.")
            else:
                surface.notice("Memory kept.")
        elif command == "/stop":
            pass  # speech was already stopped by handle()
        elif command == "/speak":
            if voice is None:
                surface.notice(NO_VOICE)
            else:
                voice.speak_replies = {"on": True, "off": False}.get(arg, not voice.speak_replies)
                surface.notice(f"Spoken replies are {'on' if voice.speak_replies else 'off'}.")
        elif command == "/wake":
            if voice is None or not voice.wake_available:
                surface.notice(NO_VOICE)
            else:
                wanted = {"on": True, "off": False}.get(arg, not voice.wake_enabled)
                on = voice.set_wake_word(wanted)
                surface.notice(f'"Hey Jarvis" listening is {"on" if on else "off"}.')
        elif command == "/personality":
            if arg in PERSONALITIES:
                self.personality.set(arg)
            else:
                self.personality.toggle()
            surface.notice(f"Personality is now {self.personality.value}.")
        elif command == "/help":
            surface.notice(HELP)
        else:
            surface.notice(f"Unknown command {text}. {HELP}")
        return True

    def _reply(self, text: str, surface: Surface) -> None:
        reply: list[str] = []
        speaking = False  # the speech thread then reports the return to idle
        self.bus.emit(State.THINKING)
        surface.reply_started()
        try:
            for chunk in self.conversation.send(text):
                reply.append(chunk)
                surface.reply_chunk(chunk)
        except LLMError as exc:
            surface.reply_failed(str(exc))
        except KeyboardInterrupt:
            surface.reply_interrupted()
        else:
            answer = "".join(reply)
            surface.reply_finished(answer)
            if self.voice is not None and self.voice.speak_replies:
                speaking = True
                self.voice.say_async(answer)  # the prompt stays free to type, talk or stop
        finally:
            if not speaking:
                self.bus.emit(State.IDLE)
