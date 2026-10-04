"""Plain "open X" / "close X" requests, handled without asking the model.

The small local model sometimes answers "Notepad has been closed" without calling the tool, so
for these two very common requests the tool is called directly. It still goes through the
permission gate, and anything that is not clearly an app (a file, a timer, an unknown name)
falls through to the model as before.
"""

import re

PATTERN = re.compile(
    r"^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
    r"(open|launch|close|quit|exit)\s+(?:up\s+)?(?:the\s+|my\s+)?(.+?)"
    r"(?:\s+(?:app|application|window|program))?(?:\s+please)?[\s.!?]*$",
    re.IGNORECASE,
)


def match_app_request(text: str) -> tuple[str, str] | None:
    """("open_app" | "close_app", app name) for a plain open/close request, else None."""
    found = PATTERN.match(text.strip())
    if found is None:
        return None
    verb, name = found.group(1).lower(), found.group(2).strip()
    if not name or len(name.split()) > 3:
        return None
    return ("open_app" if verb in ("open", "launch") else "close_app"), name


def direct_call(text: str) -> tuple[str, dict] | None:
    """The tool call to make for `text` without the model, or None to leave it to the model."""
    from jarvis.tools.apps import is_known_app, is_running

    request = match_app_request(text)
    if request is None:
        return None
    tool, name = request
    if tool == "open_app" and is_known_app(name):
        return tool, {"name": name}
    if tool == "close_app" and (is_known_app(name) or is_running(name)):
        return tool, {"name": name}
    return None


def reply_for(tool: str, arguments: dict, result: str) -> str:
    """What Jarvis says after a direct call: the tool's own result, in plain words."""
    if result.startswith("The user declined"):
        verb = "open" if tool == "open_app" else "close"
        return f"Okay, I did not {verb} {arguments['name']}."
    return result.removeprefix("Error: ")
