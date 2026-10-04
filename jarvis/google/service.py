"""Shared Google client access for the Gmail and Calendar tools."""

import functools
import logging
from collections.abc import Callable

from googleapiclient.errors import HttpError

from jarvis.core.config import Settings
from jarvis.google.auth import GoogleError, build_service

logger = logging.getLogger("jarvis.google")

_settings: Settings | None = None


def configure(settings: Settings | None) -> None:
    """Choose the settings the Google tools use. Called once at startup."""
    global _settings
    _settings = settings


def service(name: str, version: str):
    """A Google API client. Never opens the browser: an expired login raises `GoogleError`."""
    if _settings is None:
        raise GoogleError("Google is not set up.")
    return build_service(_settings, name, version, interactive=False)


def google_tool(func: Callable[..., str]) -> Callable[..., str]:
    """Turn Google failures into error text for the LLM instead of exceptions."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> str:
        try:
            return func(*args, **kwargs)
        except GoogleError as exc:
            return f"Error: {exc}"
        except HttpError as exc:
            logger.warning("Google API error: %s", exc)
            return f"Error: Google rejected the request ({exc.status_code}: {exc.reason})."
        except (OSError, TimeoutError) as exc:  # includes network failures
            logger.warning("Google network error: %s", exc)
            return f"Error: could not reach Google ({exc})."

    return wrapper
