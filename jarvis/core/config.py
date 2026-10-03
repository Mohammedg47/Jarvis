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
        env_file=".env", env_prefix="JARVIS_", extra="ignore", populate_by_name=True
    )

    # ElevenLabs uses its own conventional variable name, without the JARVIS_ prefix.
    elevenlabs_api_key: str = Field(default="", validation_alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = ""

    ollama_model: str = "llama3.1:8b"
    personality: Literal["playful", "formal"] = "playful"
    push_to_talk_hotkey: str = "ctrl+space"

    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=default_data_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
