import pytest

from jarvis.core.assistant import HELP, Assistant
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, Notifier, State
from jarvis.core.personality import PersonalityControl
from jarvis.llm.client import LLMError
from jarvis.memory import MemoryStore


class FakeSurface:
    def __init__(self, yes=True):
        self.events = []
        self.yes = yes

    def notice(self, text):
        self.events.append(("notice", text))

    def reply_started(self):
        self.events.append(("start",))

    def reply_chunk(self, text):
        self.events.append(("chunk", text))

    def reply_finished(self, text):
        self.events.append(("done", text))

    def reply_failed(self, text):
        self.events.append(("failed", text))

    def reply_interrupted(self):
        self.events.append(("interrupted",))

    def ask_yes_no(self, question):
        self.events.append(("ask", question))
        return self.yes

    def notices(self):
        return [e[1] for e in self.events if e[0] == "notice"]


def chat(messages, tools=None):
    yield "Hello "
    yield "there"


def make(tmp_path=None, chat_fn=chat):
    memory = MemoryStore(tmp_path / "m.db") if tmp_path else None
    convo = Conversation(chat_fn, "sys", None, memory, help_prompt="HELP")
    bus = EventBus()
    states = []
    bus.subscribe(states.append)
    return Assistant(convo, memory, None, PersonalityControl("playful"), bus), states


def test_a_message_streams_through_the_surface_and_cycles_the_state():
    assistant, states = make()
    surface = FakeSurface()
    assert assistant.handle("hi", surface) is True
    assert surface.events == [
        ("start",),
        ("chunk", "Hello "),
        ("chunk", "there"),
        ("done", "Hello there"),
    ]
    assert states == [State.THINKING, State.IDLE]


def test_llm_errors_are_reported_not_raised():
    def broken(messages, tools=None):
        raise LLMError("Cannot reach Ollama")
        yield

    assistant, states = make(chat_fn=broken)
    surface = FakeSurface()
    assert assistant.handle("hi", surface) is True
    assert ("failed", "Cannot reach Ollama") in surface.events
    assert states[-1] == State.IDLE


def test_exit_and_empty_lines():
    assistant, _ = make()
    assert assistant.handle("/exit", FakeSurface()) is False
    assert assistant.handle("/quit", FakeSurface()) is False
    surface = FakeSurface()
    assert assistant.handle("   ", surface) is True and surface.events == []


def test_clear_help_and_unknown_commands():
    assistant, _ = make()
    surface = FakeSurface()
    list(assistant.conversation.send("hi"))
    assistant.handle("/clear", surface)
    assert len(assistant.conversation.messages) == 1
    assistant.handle("/help", surface)
    assistant.handle("/nope", surface)
    assert surface.notices()[0] == "Conversation cleared."
    assert surface.notices()[1] == HELP
    assert surface.notices()[2].startswith("Unknown command /nope")


def test_personality_command_sets_toggles_and_notifies():
    assistant, _ = make()
    seen = []
    assistant.personality.subscribe(seen.append)
    surface = FakeSurface()
    assistant.handle("/personality formal", surface)
    assistant.handle("/personality", surface)
    assert seen == ["formal", "playful"]
    assert surface.notices() == ["Personality is now formal.", "Personality is now playful."]


def test_forget_needs_a_yes(tmp_path):
    assistant, _ = make(tmp_path)
    list(assistant.conversation.send("remember me"))
    no = FakeSurface(yes=False)
    assistant.handle("/forget", no)
    assert no.notices() == ["Memory kept."] and assistant.memory.recent_messages(5)
    yes = FakeSurface(yes=True)
    assistant.handle("/forget", yes)
    assert yes.notices() == ["Memory wiped."] and not assistant.memory.recent_messages(5)


def test_stuck_turns_help_mode_on_and_off_and_sends_the_topic():
    assistant, _ = make()
    surface = FakeSurface()
    assistant.handle("/stuck", surface)
    assert assistant.conversation.help_mode and "stuck on" in surface.notices()[0]
    assert not any(e[0] == "start" for e in surface.events)  # nothing sent yet
    assistant.handle("/stuck off", surface)
    assert not assistant.conversation.help_mode
    assistant.handle("/stuck my wifi is down", surface)
    assert assistant.conversation.help_mode
    assert ("done", "Hello there") in surface.events
    assert assistant.conversation.messages[-2]["content"] == "my wifi is down"


@pytest.mark.parametrize("command", ["/speak", "/wake"])
def test_voice_commands_without_voice_say_so(command):
    assistant, _ = make()
    surface = FakeSurface()
    assistant.handle(command, surface)
    assert "Voice is not available" in surface.notices()[0]


def test_notifier_reaches_every_subscriber_and_survives_a_failure():
    notifier = Notifier()
    seen = []

    def broken(message):
        raise RuntimeError("boom")

    notifier.subscribe(broken)
    notifier.subscribe(seen.append)
    notifier.notify("Meeting in 10 minutes")
    assert seen == ["Meeting in 10 minutes"]
