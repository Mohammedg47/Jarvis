import numpy as np

from jarvis.core.events import EventBus, State
from jarvis.voice import audio
from jarvis.voice.session import VoiceSession
from jarvis.voice.wakeword import WakeDetector

BLOCK = np.zeros(1280, dtype="int16")


def test_detector_fires_above_the_threshold_only():
    scores = iter([0.1, 0.49, 0.5, 0.9])
    detector = WakeDetector(lambda block: next(scores), 0.5, cooldown=0)
    assert [detector.feed(BLOCK) for _ in range(4)] == [False, False, True, True]


def test_detector_cooldown_stops_double_triggers():
    now = {"t": 0.0}
    detector = WakeDetector(lambda block: 0.9, 0.5, cooldown=2.0, clock=lambda: now["t"])
    assert detector.feed(BLOCK) is True
    now["t"] = 1.0
    assert detector.feed(BLOCK) is False
    now["t"] = 2.5
    assert detector.feed(BLOCK) is True


def run_wait(levels):
    """Run wait_for_end_of_speech over a list of loudness readings; return how many were read."""
    readings = iter(levels)
    count = {"n": 0}

    def loudness():
        count["n"] += 1
        return next(readings, 0.0)

    audio.wait_for_end_of_speech(loudness, sleep=lambda s: None)
    return count["n"]


def test_recording_ends_after_speech_then_a_pause():
    loud, quiet = audio.SPEECH_RMS + 1, 0.0
    steps = int(audio.SILENCE_SECONDS / 0.1)
    assert run_wait([quiet] * 3 + [loud] * 5 + [quiet] * 50) in range(8 + steps - 1, 8 + steps + 2)


def test_recording_gives_up_when_nothing_is_said():
    assert run_wait([]) in range(
        int(audio.NO_SPEECH_SECONDS / 0.1) - 1, int(audio.NO_SPEECH_SECONDS / 0.1) + 2
    )


class FakeVoice:
    pass


def make_session(bus=None):
    return VoiceSession(FakeVoice(), "ctrl+space", lambda text: None, bus=bus, wake_dir=None)


def test_wake_word_is_unavailable_without_a_model_folder():
    session = make_session()
    assert not session.wake_available
    assert session.set_wake_word(True) is False


def test_wake_is_ignored_while_a_request_is_in_progress(monkeypatch):
    bus = EventBus()
    session = make_session(bus)
    started = []
    monkeypatch.setattr(session, "_begin_recording", lambda: started.append(1) or False)
    bus.emit(State.THINKING)
    session._wake_heard()
    assert started == []
    bus.emit(State.IDLE)
    session._wake_heard()
    assert started == [1]
