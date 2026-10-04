"""Google OAuth login with a locally stored token and minimal scopes."""

import logging
from pathlib import Path

from google.auth.exceptions import GoogleAuthError as _GoogleAuthLibError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jarvis.core.config import Settings

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GoogleError(Exception):
    """A Google login or API problem, with a message fit to show the user."""


def credentials_path(settings: Settings) -> Path:
    return settings.google_credentials or settings.data_dir / "credentials.json"


def token_path(settings: Settings) -> Path:
    return settings.data_dir / "token.json"


def get_credentials(settings: Settings, interactive: bool = True) -> Credentials:
    """Return valid credentials, reusing/refreshing the saved token or opening the browser login.

    With `interactive=False` (background polling) the browser is never opened; a missing or
    unusable token raises `GoogleError` instead.
    """
    token_file = token_path(settings)
    creds: Credentials | None = None
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except (ValueError, KeyError):
            log.warning("Ignoring unreadable %s", token_file)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(token_file, creds)
            return creds
        except (_GoogleAuthLibError, OSError) as exc:
            log.info("Token refresh failed (%s); login needed", exc)

    if not interactive:
        raise GoogleError(
            "Google login has expired. Run `python -m jarvis.google` to sign in again."
        )
    return _login(settings, token_file)


def _login(settings: Settings, token_file: Path) -> Credentials:
    secrets = credentials_path(settings)
    if not secrets.exists():
        raise GoogleError(f"Google credentials not found at {secrets}. See docs/google-setup.md.")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
    except (ValueError, OSError, _GoogleAuthLibError) as exc:
        raise GoogleError(f"Google login failed: {exc}") from exc
    _save(token_file, creds)
    return creds


def _save(token_file: Path, creds: Credentials) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")


def build_service(settings: Settings, name: str, version: str, interactive: bool = True):
    """Build a Google API client (`"gmail", "v1"` or `"calendar", "v3"`)."""
    creds = get_credentials(settings, interactive)
    return build(name, version, credentials=creds, cache_discovery=False)
