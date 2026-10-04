"""Hands-free activation: listen for "Hey Jarvis" with a local openWakeWord model.

The audio never leaves the laptop: the microphone is read in small blocks and scored on the
CPU; nothing is recorded or uploaded until the wake word is heard.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd

from jarvis.voice.audio import SAMPLE_RATE
from jarvis.voice.errors import VoiceError, explain

logger = logging.getLogger("jarvis.voice")

MODEL_NAME = "hey_jarvis"
BLOCK_SAMPLES = 1280  # 80 ms at 16 kHz: the block size openWakeWord expects
COOLDOWN_SECONDS = 2.0  # one phrase must not trigger twice
FEATURE_FILES = ("melspectrogram.onnx", "embedding_model.onnx")


class WakeDetector:
    """Scores audio blocks and says when the wake word was just heard."""

    def __init__(
        self,
        predict: Callable[[np.ndarray], float],
        threshold: float = 0.5,
        cooldown: float = COOLDOWN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._predict = predict
        self.threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._quiet_until = 0.0

    def feed(self, block: np.ndarray) -> bool:
        score = self._predict(block)  # always score, so the model's own state keeps moving
        now = self._clock()
        if score >= self.threshold and now >= self._quiet_until:
            self._quiet_until = now + self._cooldown
            return True
        return False


def model_files(folder: Path) -> list[Path]:
    return [folder / f"{MODEL_NAME}_v0.1.onnx", *(folder / name for name in FEATURE_FILES)]


def ensure_models(folder: Path) -> None:
    """Download the wake word and feature models on first use (about 4 MB)."""
    if all(path.exists() for path in model_files(folder)):
        return
    from openwakeword.utils import download_models

    folder.mkdir(parents=True, exist_ok=True)
    try:
        download_models([MODEL_NAME], target_directory=str(folder))
    except Exception as exc:
        raise VoiceError(f"Could not download the wake word model: {exc}") from exc


def load_predictor(folder: Path) -> Callable[[np.ndarray], float]:
    ensure_models(folder)
    from openwakeword.model import Model

    wake, melspec, embedding = model_files(folder)
    model = Model(
        wakeword_models=[str(wake)],
        inference_framework="onnx",
        melspec_model_path=str(melspec),
        embedding_model_path=str(embedding),
    )

    def predict(block: np.ndarray) -> float:
        scores = model.predict(block)
        return max(scores.values(), default=0.0)

    return predict


class WakeWordListener:
    """Reads the microphone in the background and calls `on_wake` when "Hey Jarvis" is heard."""

    def __init__(
        self,
        on_wake: Callable[[], None],
        model_dir: Path,
        threshold: float = 0.5,
    ) -> None:
        self._on_wake = on_wake
        self._model_dir = model_dir
        self._threshold = threshold
        self._blocks: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=100)
        self._stream: sd.InputStream | None = None
        self._thread: threading.Thread | None = None
        self.paused = False  # set while Jarvis is busy, so he never wakes himself

    @property
    def running(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        """Load the model and open the microphone. Raises VoiceError if either fails."""
        if self.running:
            return
        try:
            predict = load_predictor(self._model_dir)
        except VoiceError:
            raise
        except Exception as exc:
            logger.exception("Wake word model failed to load")
            raise VoiceError(f"The wake word model could not be loaded: {exc}") from exc
        detector = WakeDetector(predict, self._threshold)
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=BLOCK_SAMPLES,
                callback=self._on_audio,
            )
            stream.start()
        except Exception as exc:  # no mic, device busy, permission denied
            raise explain(exc) from exc
        self._stream = stream
        self._thread = threading.Thread(
            target=self._work, args=(detector,), name="jarvis-wakeword", daemon=True
        )
        self._thread.start()

    def _on_audio(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        try:
            self._blocks.put_nowait(indata[:, 0].copy())
        except queue.Full:  # scoring fell behind; dropping audio beats growing without bound
            pass

    def _work(self, detector: WakeDetector) -> None:
        while True:
            block = self._blocks.get()
            if block is None:
                return
            if self.paused:
                continue
            try:
                heard = detector.feed(block)
            except Exception:
                logger.exception("Wake word scoring failed")
                continue
            if heard:
                logger.info("Wake word heard")
                try:
                    self._on_wake()
                except Exception:
                    logger.exception("Wake word handler failed")

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        while not self._blocks.empty():
            self._blocks.get_nowait()
        if self._thread is not None:
            self._blocks.put(None)
            self._thread.join(timeout=2)
            self._thread = None
