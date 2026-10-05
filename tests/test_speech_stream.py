import threading
import time

import numpy as np

from jarvis.core.assistant import Assistant
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, State
from jarvis.core.personality import PersonalityControl
from jarvis.llm.client import OllamaClient
from jarvis.voice.speech_stream import MIN_CHARS, SpeechStream, split_sentences


def test_split_keeps_the_unfinished_tail():
    done, rest = split_sentences("Hello there, how are you today? I am fine and")
    assert done == ["Hello there, how are you today?"] and rest == "I am fine and"


def test_short_sentences_are_joined_and_decimals_are_not_split():
    done, rest = split_sentences("Yes. It costs 3.50 dollars in total. Anything else?")
    assert done == ["Yes. It costs 3.50 dollars in total."] and rest == "Anything else?"
    assert all(len(s) >= MIN_CHARS for s in done)


def test_split_on_newlines():
    done, rest = split_sentences("First line is long enough to count\nsecond")
    assert done == ["First line is long enough to count"] and rest == "second"


class Recorder:
    def __init__(self):
        self.synthesized, self.played = [], []
        self.events = []
        self.done = threading.Event()
        self.current = True

    def stream(self):
        return SpeechStream(
            synthesize=lambda text: (self.synthesized.append(text), np.zeros(4, "int16"))[1],
            play=lambda pcm: self.played.append(len(pcm)),
            is_current=lambda: self.current,
            on_start=lambda: self.events.append("start"),
            on_end=lambda: (self.events.append("end"), self.done.set()),
            on_error=lambda exc: self.events.append(f"error: {exc}"),
        )


def test_sentences_are_spoken_as_they_arrive_then_the_stream_ends():
    rec = Recorder()
    stream = rec.stream()
    for chunk in ["This is the first sentence. ", "And here is the second", " one. Bye"]:
        stream.feed(chunk)
    stream.finish()
    assert rec.done.wait(3)
    assert rec.synthesized == [
        "This is the first sentence.",
        "And here is the second one.",
        "Bye",
    ]
    assert len(rec.played) == 3 and rec.events == ["start", "end"]


def test_cancel_stops_without_ending_normally():
    rec = Recorder()
    stream = rec.stream()
    stream.cancel()
    time.sleep(0.2)
    assert rec.events == [] and rec.played == []


def test_a_superseded_stream_stays_silent():
    rec = Recorder()
    rec.current = False  # a newer message took over
    stream = rec.stream()
    stream.feed("This sentence should never be spoken at all. ")
    stream.finish()
    time.sleep(0.3)
    assert rec.played == [] and rec.events == []


def test_synthesis_errors_are_reported_and_speech_still_ends():
    events = []
    done = threading.Event()

    def broken(text):
        raise RuntimeError("quota")

    stream = SpeechStream(
        broken,
        lambda pcm: None,
        lambda: True,
        lambda: events.append("start"),
        lambda: (events.append("end"), done.set()),
        lambda exc: events.append(f"error: {exc}"),
    )
    stream.feed("A sentence that is long enough to speak. ")
    stream.finish()
    assert done.wait(3) and events == ["error: quota", "end"]


class FakeVoice:
    speak_replies = True

    def __init__(self):
        self.stream = None

    def stop_speaking(self):
        pass

    def begin_stream(self):
        self.stream = Streamed()
        return self.stream


class Streamed:
    def __init__(self):
        self.fed, self.finished, self.cancelled = [], False, False

    def feed(self, chunk):
        self.fed.append(chunk)

    def finish(self):
        self.finished = True

    def cancel(self):
        self.cancelled = True


class Surface:
    def __getattr__(self, name):
        return lambda *a, **k: None


def make_assistant(chat):
    voice = FakeVoice()
    bus = EventBus()
    states = []
    bus.subscribe(states.append)
    assistant = Assistant(
        Conversation(chat, "sys"), None, voice, PersonalityControl("playful"), bus
    )
    return assistant, voice, states


def test_assistant_streams_chunks_to_speech_and_leaves_idle_to_the_stream():
    def chat(messages, tools=None):
        yield "Hello "
        yield "there."

    assistant, voice, states = make_assistant(chat)
    assistant.handle("hi", Surface())
    assert voice.stream.fed == ["Hello ", "there."] and voice.stream.finished
    assert states == [State.THINKING]  # the speech stream emits speaking/idle itself


def test_assistant_cancels_speech_when_the_model_fails():
    from jarvis.llm.client import LLMError

    def chat(messages, tools=None):
        yield "Partial "
        raise LLMError("down")

    assistant, voice, states = make_assistant(chat)
    assistant.handle("hi", Surface())
    assert voice.stream.cancelled and not voice.stream.finished
    assert states[-1] == State.IDLE


def test_keep_alive_accepts_durations_and_numbers():
    assert OllamaClient("m", "30m").keep_alive == "30m"
    assert OllamaClient("m", "-1").keep_alive == -1
