"""Ties the hotkey, microphone, speech-to-text and text-to-speech into one voice session."""

import logging
import threading
from collections.abc import Callable

from jarvis.voice import audio
from jarvis.voice.elevenlabs_io import Voice
from jarvis.voice.errors import VoiceError
from jarvis.voice.hotkey import PushToTalk

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
    ) -> None:
        self.speak_replies = speak_replies
        self._voice = voice
        self._on_transcript = on_transcript
        self._notify = notify
        self._recorder = audio.Recorder()
        self._recording = False
        self._hotkey = PushToTalk(hotkey, self._press, self._release)

    def start(self) -> bool:
        """Install the global hotkey. Returns False (after reporting) if that fails."""
        try:
            self._hotkey.start()
        except Exception as exc:
            logger.exception("Could not install the push-to-talk hotkey")
            self._notify(f"[voice error] Push-to-talk is unavailable: {exc}")
            return False
        return True

    def stop(self) -> None:
        self._hotkey.stop()

    def say(self, text: str) -> None:
        try:
            self._voice.speak(text)
        except VoiceError as exc:
            logger.warning("Speech failed: %s", exc)
            self._notify(f"[voice error] {exc}")

    def _press(self) -> None:
        audio.stop_playback()  # talking over Jarvis interrupts it
        try:
            self._recorder.start()
        except VoiceError as exc:
            self._notify(f"[voice error] {exc}")
            return
        self._recording = True
        self._notify("[listening...]")

    def _release(self) -> None:
        if not self._recording:
            return
        self._recording = False
        samples = self._recorder.stop()
        if not audio.is_long_enough(samples):
            return
        threading.Thread(target=self._transcribe, args=(samples,), daemon=True).start()

    def _transcribe(self, samples) -> None:
        try:
            text = self._voice.transcribe(samples)
        except VoiceError as exc:
            logger.warning("Transcription failed: %s", exc)
            self._notify(f"[voice error] {exc}")
            return
        if text:
            self._on_transcript(text)
        else:
            self._notify("[voice] I did not catch that.")
