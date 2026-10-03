"""Microphone recording, playback and WAV helpers."""

import io
import wave

import numpy as np
import sounddevice as sd

from jarvis.voice.errors import explain

SAMPLE_RATE = 16000  # plenty for speech, small to upload
MIN_SECONDS = 0.3  # shorter clips are accidental key taps


class Recorder:
    """Records mono 16-bit audio between `start()` and `stop()`."""

    def __init__(self) -> None:
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        if self._stream is not None:
            return
        self._frames = []
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=self._on_audio
            )
            stream.start()
        except Exception as exc:  # no mic, device busy, permission denied
            raise explain(exc) from exc
        self._stream = stream

    def _on_audio(self, indata: np.ndarray, frames: int, time, status) -> None:
        self._frames.append(indata.copy())

    def stop(self) -> np.ndarray:
        """Stop recording and return the samples (empty if nothing was captured)."""
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        if not self._frames:
            return np.zeros(0, dtype="int16")
        return np.concatenate(self._frames).reshape(-1)


def is_long_enough(samples: np.ndarray) -> bool:
    return len(samples) >= MIN_SECONDS * SAMPLE_RATE


def to_wav_bytes(samples: np.ndarray, rate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.astype("int16").tobytes())
    return buffer.getvalue()


def stop_playback() -> None:
    sd.stop()


def play(samples: np.ndarray, rate: int) -> None:
    """Play samples and block until done. Ctrl+C stops playback and re-raises."""
    try:
        sd.play(samples, rate)
        sd.wait()
    except KeyboardInterrupt:
        sd.stop()
        raise
    except Exception as exc:
        raise explain(exc) from exc
