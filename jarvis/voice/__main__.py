"""Voice smoke tests: `python -m jarvis.voice [say [text] | record | listen]`."""

import sys
import time

import numpy as np

from jarvis.core.config import get_settings
from jarvis.voice import audio
from jarvis.voice.elevenlabs_io import Voice
from jarvis.voice.errors import VoiceError

SECONDS = 4


def _record() -> np.ndarray:
    recorder = audio.Recorder()
    print(f"Recording for {SECONDS} seconds... speak now.")
    recorder.start()
    time.sleep(SECONDS)
    return recorder.stop()


def main(argv: list[str]) -> None:
    settings = get_settings()
    command = argv[0] if argv else "say"
    try:
        if command == "record":
            samples = _record()
            print("Playing it back.")
            audio.play(samples, audio.SAMPLE_RATE)
            return
        voice = Voice(settings.elevenlabs_api_key, settings.elevenlabs_voice_id)
        if command == "say":
            voice.speak(" ".join(argv[1:]) or "Hello, I am Jarvis. Voice is working.")
        elif command == "listen":
            print("Transcript:", voice.transcribe(_record()) or "(nothing heard)")
        else:
            print("Usage: python -m jarvis.voice [say [text] | record | listen]")
    except VoiceError as exc:
        print(f"[voice error] {exc}")


if __name__ == "__main__":
    main(sys.argv[1:])
