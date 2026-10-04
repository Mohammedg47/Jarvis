"""Builds the system prompt from the markdown files in `prompts/`."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def build_system_prompt(personality: str) -> str:
    base = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8").strip()
    style = (PROMPTS_DIR / f"{personality}.md").read_text(encoding="utf-8").strip()
    return f"{base}\n\n{style}"


def build_help_prompt() -> str:
    """The extra instructions added to the system prompt while help mode is on."""
    return (PROMPTS_DIR / "help.md").read_text(encoding="utf-8").strip()
