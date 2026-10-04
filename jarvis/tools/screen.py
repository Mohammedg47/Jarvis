"""Screenshot tools: save a screenshot, or look at the screen with a local vision model."""

import io
import logging
from datetime import datetime
from pathlib import Path

import mss
import mss.tools
import ollama

from jarvis.core.config import get_settings
from jarvis.tools.registry import tool

logger = logging.getLogger("jarvis.tools")

SCREENSHOT_DIR = "screenshots"
MAX_SIDE = 1280  # the vision model gets a downscaled picture: faster, and fits a 4 GB GPU
VISION_PROMPT = (
    "This is a screenshot of the user's Windows screen. {question}\n"
    "Say what is on screen (the app, what it shows, any error text), then give two or three "
    "short numbered next steps the user can take. Plain text, no markdown."
)


def capture_png() -> bytes:
    """The primary monitor as PNG bytes."""
    with mss.mss() as grabber:
        shot = grabber.grab(grabber.monitors[1])
        return mss.tools.to_png(shot.rgb, shot.size)


def _downscale(png: bytes) -> bytes:
    """Shrink a large screenshot for the vision model."""
    try:
        from PIL import Image
    except ImportError:
        return png
    image = Image.open(io.BytesIO(png))
    if max(image.size) <= MAX_SIDE:
        return png
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def save_screenshot(folder: Path | None = None) -> Path:
    folder = folder or get_settings().data_dir / SCREENSHOT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"screenshot-{datetime.now().astimezone():%Y%m%d-%H%M%S}.png"
    path.write_bytes(capture_png())
    return path


@tool()
def take_screenshot() -> str:
    """Save a screenshot of the user's screen to a file and say where it is. Use it when the user asks for a screenshot or screen capture."""
    try:
        path = save_screenshot()
    except Exception as exc:  # noqa: BLE001  (no display, grab failure)
        return f"Error: could not take a screenshot ({exc})."
    return f"Screenshot saved to {path}"


@tool()
def look_at_screen(question: str = "Describe what is on the screen.") -> str:
    """Look at the user's screen with a vision model and describe it. Use it when the user asks what is on their screen or needs help with something they can see. Answer from the description and suggest next steps.

    Args:
        question: What to find out about the screen, e.g. "What does the error say?".
    """
    settings = get_settings()
    try:
        png = _downscale(capture_png())
    except Exception as exc:  # noqa: BLE001
        return f"Error: could not take a screenshot ({exc})."
    try:
        reply = ollama.Client().chat(
            model=settings.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": VISION_PROMPT.format(question=question),
                    "images": [png],
                }
            ],
        )
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            return (
                f"Error: the vision model '{settings.vision_model}' is not installed. "
                f"Tell the user to run: ollama pull {settings.vision_model}"
            )
        return f"Error: the vision model failed ({exc.error})."
    except (ConnectionError, ollama.RequestError):
        return "Error: cannot reach Ollama to look at the screen."
    return reply.message.content or "Error: the vision model returned nothing."
