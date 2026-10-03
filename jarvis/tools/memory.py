"""Tools that let Jarvis remember and recall the user's preferences."""

from jarvis.memory import MemoryStore
from jarvis.tools.registry import tool

_store: MemoryStore | None = None


def configure(store: MemoryStore | None) -> None:
    """Choose the store the memory tools use. Called once at startup."""
    global _store
    _store = store


@tool()
def remember_preference(key: str, value: str) -> str:
    """Save something the user wants remembered for future conversations, such as a preference or a fact about them.

    Args:
        key: Short label for the preference, e.g. "theme" or "favorite music".
        value: What to remember, e.g. "dark mode".
    """
    if _store is None:
        return "Error: memory is not available."
    _store.set_preference(key, value)
    return f"Remembered: {key} = {value}"


@tool()
def recall_preferences() -> str:
    """List everything saved about the user's preferences. Use it when the user asks what you remember."""
    if _store is None:
        return "Error: memory is not available."
    prefs = _store.preferences()
    if not prefs:
        return "No preferences saved yet."
    return "\n".join(f"{k}: {v}" for k, v in prefs.items())
