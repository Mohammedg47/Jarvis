"""Sign in to Google and check access: `python -m jarvis.google`."""

from jarvis.core.config import get_settings
from jarvis.google.auth import GoogleError, build_service


def main() -> None:
    settings = get_settings()
    try:
        profile = build_service(settings, "gmail", "v1").users().getProfile(userId="me").execute()
    except GoogleError as exc:
        print(exc)
        return
    print(
        f"Signed in as {profile['emailAddress']}. Token saved to {settings.data_dir / 'token.json'}."
    )


if __name__ == "__main__":
    main()
