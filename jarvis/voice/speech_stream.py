"""Speak a reply while the model is still writing it, one sentence at a time.

Sentences are turned into audio ahead of playback (generation of the next overlaps with playing
the current one), so a long answer starts talking after its first sentence instead of after the
last one.
"""

import logging
import queue
import re
import threading
from collections.abc import Callable

import numpy as np

logger = logging.getLogger("jarvis.voice")

SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
MIN_CHARS = 25  # shorter pieces are joined to the next one, so speech is not choppy


def split_sentences(text: str) -> tuple[list[str], str]:
    """Split off the complete sentences of `text`: (sentences, unfinished remainder)."""
    parts = SENTENCE_END.split(text)
    remainder = parts.pop()  # whatever follows the last sentence end is not finished yet
    sentences: list[str] = []
    pending = ""
    for part in parts:
        pending = f"{pending} {part}".strip()
        if len(pending) >= MIN_CHARS:
            sentences.append(pending)
            pending = ""
    return sentences, f"{pending} {remainder}".strip() if pending else remainder


class SpeechStream:
    """Feed it the reply as it streams in; call `finish()` at the end or `cancel()` on failure."""

    def __init__(
        self,
        synthesize: Callable[[str], np.ndarray | None],
        play: Callable[[np.ndarray], None],
        is_current: Callable[[], bool],
        on_start: Callable[[], None],
        on_end: Callable[[], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self._synthesize = synthesize
        self._play = play
        self._is_current = is_current
        self._on_start = on_start
        self._on_end = on_end
        self._on_error = on_error
        self._text = ""
        self._cancelled = False
        self._sentences: queue.Queue[str | None] = queue.Queue()
        self._audio: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=2)
        threading.Thread(target=self._generate, name="jarvis-tts", daemon=True).start()
        threading.Thread(target=self._playback, name="jarvis-speech", daemon=True).start()

    def _alive(self) -> bool:
        return not self._cancelled and self._is_current()

    def feed(self, chunk: str) -> None:
        self._text += chunk
        ready, self._text = split_sentences(self._text)
        for sentence in ready:
            self._sentences.put(sentence)

    def finish(self) -> None:
        """The reply is complete: speak what is left, then end."""
        if self._text.strip():
            self._sentences.put(self._text.strip())
        self._text = ""
        self._sentences.put(None)

    def cancel(self) -> None:
        """Drop everything not yet spoken (the reply failed or was interrupted)."""
        self._cancelled = True
        self._sentences.put(None)

    def _generate(self) -> None:
        try:
            while self._alive():
                sentence = self._sentences.get()
                if sentence is None:
                    break
                pcm = self._synthesize(sentence)
                if pcm is not None and self._alive():
                    self._audio.put(pcm)
        except Exception as exc:  # noqa: BLE001  (API errors are reported, then speech ends)
            if self._alive():
                self._on_error(exc)
        finally:
            self._audio.put(None)

    def _playback(self) -> None:
        started = False
        while True:
            pcm = self._audio.get()
            if pcm is None:
                break
            if not self._alive():
                continue  # keep draining so the generator never blocks
            if not started:
                started = True
                self._on_start()
            try:
                self._play(pcm)
            except Exception as exc:  # noqa: BLE001
                self._on_error(exc)
                self._cancelled = True
        if not self._cancelled and self._is_current():
            self._on_end()
