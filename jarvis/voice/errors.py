"""Voice failures, each with a message that is safe to show the user."""

import httpx
from elevenlabs.core.api_error import ApiError
from sounddevice import PortAudioError


class VoiceError(Exception):
    """A voice step failed. The message says what went wrong in plain words."""


def explain(exc: Exception) -> VoiceError:
    """Turn a library exception from audio or ElevenLabs into a VoiceError."""
    if isinstance(exc, VoiceError):
        return exc
    if isinstance(exc, PortAudioError):
        return VoiceError(f"Audio device problem (is a microphone/speaker connected?): {exc}")
    if isinstance(exc, httpx.TimeoutException):
        return VoiceError("ElevenLabs did not answer in time. Check your internet connection.")
    if isinstance(exc, httpx.TransportError):
        return VoiceError("Cannot reach ElevenLabs. Check your internet connection.")
    if isinstance(exc, ApiError):
        if exc.status_code in (401, 403):
            return VoiceError("ElevenLabs rejected the API key. Check ELEVENLABS_API_KEY in .env.")
        if exc.status_code == 429:
            return VoiceError("ElevenLabs rate limit or quota reached. Try again later.")
        return VoiceError(f"ElevenLabs error (HTTP {exc.status_code}).")
    return VoiceError(f"Voice error: {exc}")
