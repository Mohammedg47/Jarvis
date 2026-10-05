"""Ties the hotkey, microphone, speech-to-text and text-to-speech into one voice session."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from jarvis.core.events import EventBus, State
from jarvis.voice import audio
from jarvis.voice.elevenlabs_io import TTS_RATE, Voice
from jarvis.voice.errors import VoiceError, explain
from jarvis.voice.hotkey import PressHotkey, PushToTalk
from jarvis.voice.speech_stream import SpeechStream
from jarvis.voice.wakeword import WakeWordListener

logger = logging.getLogger("jarvis.voice")


class VoiceSession:
    """Hold the hotkey to speak: the transcript goes to `on_transcript` like typed text.

    Every failure (no mic, no internet, API error) is reported through `notify` and never
    raised, so a voice problem leaves the text chat working.
    """

    def __init__(
        self,
        voice: Voice,
        hotkey: str,
        on_transcript: Callable[[str], None],
        notify: Callable[[str], None] = print,
        speak_replies: bool = True,
        bus: EventBus | None = None,
        stop_hotkey: str = "",
        wake_dir: Path | None = None,
        wake_threshold: float = 0.5,
    ) -> None:
        self.speak_replies = speak_replies
        self._bus = bus or EventBus()
        self._voice = voice
        self._on_transcript = on_transcript
        self._notify = notify
        self._recorder = audio.Recorder()
        self._recording = False
        self._hotkey = PushToTalk(hotkey, self._press, self._release)
        self._stop_hotkey = PressHotkey(stop_hotkey, self.stop_speaking) if stop_hotkey else None
        self._wake = (
            WakeWordListener(self._wake_heard, wake_dir, wake_threshold) if wake_dir else None
        )
        self._speech_id = 0  # bumped to cancel the speech in progress
        self._speech_lock = threading.Lock()

    def start(self) -> bool:
        """Install the global hotkey. Returns False (after reporting) if that fails."""
        try:
            self._hotkey.start()
            if self._stop_hotkey is not None:
                self._stop_hotkey.start()
        except Exception as exc:
            logger.exception("Could not install the push-to-talk hotkey")
            self._notify(f"[voice error] Push-to-talk is unavailable: {exc}")
            return False
        return True

    def stop(self) -> None:
        self.set_wake_word(False)
        self._hotkey.stop()
        if self._stop_hotkey is not None:
            self._stop_hotkey.stop()

    @property
    def wake_available(self) -> bool:
        return self._wake is not None

    @property
    def wake_enabled(self) -> bool:
        return self._wake is not None and self._wake.running

    def set_wake_word(self, on: bool) -> bool:
        """Turn "Hey Jarvis" listening on or off. Returns whether it is on afterwards; a failure
        (no model, no mic) is reported through `notify` and leaves it off."""
        if self._wake is None:
            return False
        if on:
            try:
                self._wake.start()
            except VoiceError as exc:
                logger.warning("Wake word unavailable: %s", exc)
                self._notify(f"[voice error] Wake word is unavailable: {exc}")
        else:
            self._wake.stop()
        return self._wake.running

    def _wake_heard(self) -> None:
        """ "Hey Jarvis": record hands-free until the user stops talking, then handle it like a
        push-to-talk clip. Ignored while a request is already being handled."""
        if self._recording or self._bus.state in (State.LISTENING, State.THINKING):
            return
        self.stop_speaking()
        if self._begin_recording():
            threading.Thread(target=self._record_hands_free, daemon=True).start()

    def _record_hands_free(self) -> None:
        self._wake.paused = True
        try:
            audio.wait_for_end_of_speech(lambda: self._recorder.last_rms)
            self._finish_recording()
        finally:
            self._wake.paused = False

    def stop_speaking(self) -> None:
        """Cut off the speech in progress, including audio still being generated."""
        with self._speech_lock:
            self._speech_id += 1
        audio.stop_playback()
        if self._bus.state == State.SPEAKING:
            self._bus.emit(State.IDLE)

    def say(self, text: str) -> None:
        """Speak and wait until done. Replaces any speech already in progress."""
        with self._speech_lock:
            self._speech_id += 1
            mine = self._speech_id
        audio.stop_playback()
        self._bus.emit(State.SPEAKING)
        try:
            self._voice.speak(text, should_play=lambda: self._speech_id == mine)
        except VoiceError as exc:
            logger.warning("Speech failed: %s", exc)
            self._notify(f"[voice error] {exc}")
        finally:
            if self._speech_id == mine:  # a newer speech owns the state otherwise
                self._bus.emit(State.IDLE)

    def begin_stream(self) -> SpeechStream:
        """Start speaking a reply that is still being written (see SpeechStream). Replaces any
        speech in progress; `stop_speaking` cuts it off like any other."""
        with self._speech_lock:
            self._speech_id += 1
            mine = self._speech_id
        audio.stop_playback()

        def is_current() -> bool:
            return self._speech_id == mine

        def on_error(exc: Exception) -> None:
            error = explain(exc)
            logger.warning("Speech failed: %s", error)
            self._notify(f"[voice error] {error}")
            if is_current():
                self._bus.emit(State.IDLE)

        return SpeechStream(
            synthesize=self._voice.synthesize,
            play=lambda pcm: audio.play(pcm, TTS_RATE),
            is_current=is_current,
            on_start=lambda: self._bus.emit(State.SPEAKING),
            on_end=lambda: self._bus.emit(State.IDLE),
            on_error=on_error,
        )

    def say_async(self, text: str) -> None:
        """Speak in the background so the prompt stays free to type, talk or stop."""
        threading.Thread(target=self.say, args=(text,), daemon=True).start()

    def _press(self) -> None:
        self.stop_speaking()  # talking over Jarvis interrupts it
        self._begin_recording()

    def _begin_recording(self) -> bool:
        try:
            self._recorder.start()
        except VoiceError as exc:
            self._notify(f"[voice error] {exc}")
            return False
        self._recording = True
        self._bus.emit(State.LISTENING)
        self._notify("[listening...]")
        return True

    def _release(self) -> None:
        self._finish_recording()

    def _finish_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        samples = self._recorder.stop()
        if not audio.is_long_enough(samples):
            self._bus.emit(State.IDLE)
            return
        self._bus.emit(State.THINKING)  # transcribing; the CLI keeps it there while replying
        threading.Thread(target=self._transcribe, args=(samples,), daemon=True).start()

    def _transcribe(self, samples) -> None:
        try:
            text = self._voice.transcribe(samples)
        except VoiceError as exc:
            logger.warning("Transcription failed: %s", exc)
            self._notify(f"[voice error] {exc}")
            self._bus.emit(State.IDLE)
            return
        if text:
            self._on_transcript(text)
        else:
            self._notify("[voice] I did not catch that.")
            self._bus.emit(State.IDLE)
