"""Application settings, loaded from environment variables and a local `.env` file."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    """Per-user data directory (logs, later the memory DB), outside the repo."""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Jarvis"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(default_data_dir() / ".env"), ".env"),
        env_prefix="JARVIS_",
        extra="ignore",
        populate_by_name=True,
    )

    # ElevenLabs uses its own conventional variable name, without the JARVIS_ prefix.
    elevenlabs_api_key: str = Field(default="", validation_alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = ""

    # Speak replies aloud (needs an ElevenLabs key). Toggle live with /speak.
    speak_replies: bool = True

    # Show the floating character (needs a real console). Turn off for a terminal-only Jarvis.
    show_character: bool = True
    # Let the idle character wander around the screen (it stays put while Jarvis is busy).
    character_roam: bool = False
    # "noto" = premade animated emoji (GIFs); "drawn" = the code-drawn face.
    character_style: Literal["noto", "drawn"] = "noto"

    ollama_model: str = "qwen2.5:3b"
    # How long Ollama keeps the model loaded when idle ("30m", "2h", "-1" = forever). A longer
    # time avoids a ~15 s reload, but holds about 2 GB of GPU memory.
    ollama_keep_alive: str = "30m"
    # Vision model for look_at_screen (run `ollama pull qwen2.5vl:3b` once).
    vision_model: str = "qwen2.5vl:3b"
    personality: Literal["playful", "formal"] = "playful"
    push_to_talk_hotkey: str = "ctrl+space"
    # Say "Hey Jarvis" to talk hands-free (needs voice). Runs locally; audio is only sent for
    # transcription after the wake word. Toggle live with /wake or the tray.
    wake_word: bool = True
    wake_threshold: float = 0.5  # raise it if Jarvis wakes by mistake, lower it if he misses you
    # Press to stop Jarvis talking, from any app. Empty disables it. Also: /stop, or just talk.
    stop_hotkey: str = "esc"
    # Press to start help mode ("I need help"), from any app. Empty disables it. Also: /stuck.
    help_hotkey: str = "ctrl+alt+h"

    # Extra apps for open_app, as JSON: {"spotify": "spotify.exe"}. Merged over the built-in map.
    apps: dict[str, str] = Field(default_factory=dict)
    # Folders the file tools may touch, as a JSON list. Empty means the standard user folders.
    file_roots: list[Path] = Field(default_factory=list)

    # OAuth client file from Google Cloud (see docs/google-setup.md). Default: <data dir>\credentials.json.
    google_credentials: Path | None = None

    # Proactive alerts (Google). Each can be turned off; a disabled one is never polled.
    alert_events: bool = True
    alert_important_email: bool = True
    alert_event_minutes: int = 10  # warn this long before an event starts
    alert_poll_minutes: int = 5
    alert_email_label: str = "IMPORTANT"  # Gmail label that counts as important

    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=default_data_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
