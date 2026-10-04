import io
import wave

import httpx
import numpy as np
import pytest
from elevenlabs.core.api_error import ApiError

from jarvis.ui.cli import Reader, is_yes
from jarvis.voice import audio
from jarvis.voice.elevenlabs_io import Voice, clean_for_speech
from jarvis.voice.errors import VoiceError, explain
from jarvis.voice.hotkey import HoldTracker
from jarvis.voice.session import VoiceSession


class FakeVoice:
    def __init__(self, text="hello", error=None):
        self.text, self.error, self.spoken = text, error, []

    def speak(self, text, should_play=lambda: True):
        if self.error:
            raise self.error
        self.spoken.append(text)

    def transcribe(self, samples):
        if self.error:
            raise self.error
        return self.text


def test_voice_requires_api_key():
    with pytest.raises(VoiceError, match="ELEVENLABS_API_KEY"):
        Voice("")


def test_clean_for_speech_strips_markdown():
    assert clean_for_speech("**Hi** `there`\n\n# Done") == "Hi there Done"


def test_wav_bytes_round_trip():
    samples = np.arange(100, dtype="int16")
    with wave.open(io.BytesIO(audio.to_wav_bytes(samples)), "rb") as wav:
        assert (wav.getnchannels(), wav.getframerate(), wav.getnframes()) == (1, 16000, 100)


def test_short_clips_are_ignored():
    assert not audio.is_long_enough(np.zeros(100, dtype="int16"))
    assert audio.is_long_enough(np.zeros(16000, dtype="int16"))


def test_hold_tracker_starts_on_press_and_stops_on_release():
    events = []
    tracker = HoldTracker(
        "ctrl+space", lambda: events.append("start"), lambda: events.append("stop")
    )
    tracker.key_event("space", True)  # ctrl not down yet
    tracker.key_event("space", False)
    assert events == []
    tracker.key_event("ctrl", True)
    tracker.key_event("space", True)
    tracker.key_event("space", True)  # key repeat must not restart
    tracker.key_event("ctrl", False)
    tracker.key_event("space", False)
    assert events == ["start", "stop"]


def test_explain_gives_clear_messages():
    assert "internet" in str(explain(httpx.ConnectError("x")))
    assert "API key" in str(explain(ApiError(status_code=401, body="no")))
    assert "quota" in str(explain(ApiError(status_code=429, body="slow")))


@pytest.mark.parametrize("answer", ["yes", "Yes.", "y", "yeah sure", "OK"])
def test_is_yes(answer):
    assert is_yes(answer)


@pytest.mark.parametrize("answer", ["no", "", "No, don't", "maybe", "nope yes"])
def test_is_not_yes(answer):
    assert not is_yes(answer)


def test_session_reports_errors_instead_of_raising():
    notes = []
    session = VoiceSession(
        FakeVoice(error=VoiceError("Cannot reach ElevenLabs.")), "ctrl+space", print, notes.append
    )
    session.say("hi")
    session._transcribe(np.zeros(10, dtype="int16"))
    assert notes == ["[voice error] Cannot reach ElevenLabs."] * 2


def test_session_delivers_transcript():
    got = []
    session = VoiceSession(FakeVoice("open notepad"), "ctrl+space", got.append, lambda m: None)
    session._transcribe(np.zeros(10, dtype="int16"))
    assert got == ["open notepad"]


def test_session_reports_no_microphone(monkeypatch):
    notes = []
    session = VoiceSession(FakeVoice(), "ctrl+space", print, notes.append)

    def broken():
        raise VoiceError("Audio device problem")

    monkeypatch.setattr(session._recorder, "start", broken)
    session._press()
    session._release()  # nothing was recorded, must not crash
    assert notes == ["[voice error] Audio device problem"]


def test_reader_returns_injected_voice_line_first(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    reader = Reader()
    reader.inject("hello jarvis")
    assert reader.ask("You: ") == "hello jarvis"


def test_reader_fresh_drops_old_voice_lines(monkeypatch):
    reader = Reader()
    reader._session = None
    reader.inject("stale")
    monkeypatch.setattr("builtins.input", lambda label: "typed")
    assert reader.ask("Allow? ", fresh=True) == "typed"


def test_stop_speaking_cancels_speech_and_returns_to_idle(monkeypatch):
    import threading

    from jarvis.core.events import EventBus, State
    from jarvis.voice import audio
    from jarvis.voice.session import VoiceSession

    stopped = []
    monkeypatch.setattr(audio, "stop_playback", lambda: stopped.append(True))
    release = threading.Event()
    played: list[str] = []

    class FakeVoice:
        def speak(self, text, should_play=lambda: True):
            release.wait(2)  # the audio is "being generated"
            if should_play():
                played.append(text)

    bus = EventBus()
    session = VoiceSession(FakeVoice(), "ctrl+space", lambda t: None, bus=bus)
    thread = threading.Thread(target=session.say, args=("hello",))
    thread.start()
    while bus.state != State.SPEAKING:
        pass
    session.stop_speaking()
    assert bus.state == State.IDLE
    release.set()
    thread.join()
    assert played == []  # stopped before the audio was ready, so it never plays
    assert stopped


def test_reader_injected_overlay_line_is_returned(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    reader = Reader()
    reader.inject("what time is it", "overlay")
    assert reader.ask("You: ") == "what time is it"
