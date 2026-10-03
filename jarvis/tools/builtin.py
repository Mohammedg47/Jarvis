"""Built-in tools available from the start."""

from datetime import datetime

from jarvis.tools.registry import tool


@tool()
def get_time() -> str:
    """Get the current local date and time. Use it when the user asks what time or day it is."""
    return datetime.now().astimezone().strftime("%A, %d %B %Y, %H:%M")
