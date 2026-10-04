"""Ties the hotkey, microphone, speech-to-text and text-to-speech into one voice session."""

import logging
import threading
from collections.abc import Callable

from jarvis.core.events import EventBus, State
from jarvis.voice import audio
from jarvis.voice.elevenlabs_io import Voice
from jarvis.voice.errors import VoiceError
from jarvis.voice.hotkey import PressHotkey, PushToTalk

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
        self._hotkey.stop()
        if self._stop_hotkey is not None:
            self._stop_hotkey.stop()

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

    def say_async(self, text: str) -> None:
        """Speak in the background so the prompt stays free to type, talk or stop."""
        threading.Thread(target=self.say, args=(text,), daemon=True).start()

    def _press(self) -> None:
        self.stop_speaking()  # talking over Jarvis interrupts it
        try:
            self._recorder.start()
        except VoiceError as exc:
            self._notify(f"[voice error] {exc}")
            return
        self._recording = True
        self._bus.emit(State.LISTENING)
        self._notify("[listening...]")

    def _release(self) -> None:
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
