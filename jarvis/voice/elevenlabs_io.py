"""ElevenLabs text-to-speech and speech-to-text."""

import re
from collections.abc import Callable

import numpy as np
from elevenlabs.client import ElevenLabs

from jarvis.voice import audio
from jarvis.voice.errors import VoiceError, explain

DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # "George", a stock ElevenLabs voice
TTS_MODEL = "eleven_flash_v2_5"
STT_MODEL = "scribe_v1"
TTS_RATE = 24000  # matches output_format pcm_24000

_MARKDOWN = re.compile(r"[*_`#>]+")


def clean_for_speech(text: str) -> str:
    """Drop markdown symbols the voice would read aloud."""
    return re.sub(r"\s+", " ", _MARKDOWN.sub("", text)).strip()


class Voice:
    """Speaks text and transcribes recorded audio. Needs an ElevenLabs API key."""

    def __init__(self, api_key: str, voice_id: str = "") -> None:
        if not api_key:
            raise VoiceError("No ElevenLabs API key. Set ELEVENLABS_API_KEY in .env.")
        self._client = ElevenLabs(api_key=api_key)
        self._voice_id = voice_id or DEFAULT_VOICE_ID

    def speak(self, text: str, should_play: Callable[[], bool] = lambda: True) -> None:
        """Speak text. `should_play` is checked once the audio is ready, so speech that was
        stopped while it was being generated stays silent."""
        text = clean_for_speech(text)
        if not text:
            return
        try:
            chunks = self._client.text_to_speech.convert(
                self._voice_id, text=text, model_id=TTS_MODEL, output_format="pcm_24000"
            )
            pcm = b"".join(chunks)
        except Exception as exc:
            raise explain(exc) from exc
        if not should_play():
            return
        audio.play(np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="int16"), TTS_RATE)

    def transcribe(self, samples: np.ndarray) -> str:
        """Send recorded samples to speech-to-text and return the transcript."""
        wav = audio.to_wav_bytes(samples)
        try:
            result = self._client.speech_to_text.convert(
                model_id=STT_MODEL,
                file=("speech.wav", wav, "audio/wav"),
                tag_audio_events=False,
            )
        except Exception as exc:
            raise explain(exc) from exc
        return (result.text or "").strip()
