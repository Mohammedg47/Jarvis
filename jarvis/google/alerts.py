"""Proactive alerts: upcoming calendar events and new important email, polled in the background.

Each alert type has its own on/off setting; a disabled one is never polled. Polling never
opens a browser: if the login has expired, one notice is sent and that poller stops.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from jarvis.core.config import Settings
from jarvis.google.auth import GoogleError, token_path
from jarvis.google.service import service
from jarvis.tools.gmail import header

logger = logging.getLogger("jarvis.google.alerts")


class AlertPoller:
    def __init__(self, settings: Settings, alert: Callable[[str], None]) -> None:
        self._settings = settings
        self._alert = alert
        self._scheduler: BackgroundScheduler | None = None
        self._seen_events: set[str] = set()
        self._seen_mail: set[str] | None = None  # None until the first poll sets the baseline

    def start(self) -> list[str]:
        """Start the enabled pollers and return their names (empty if nothing runs)."""
        s = self._settings
        wanted = {"event": s.alert_events, "email": s.alert_important_email}
        if not any(wanted.values()):
            return []
        if not token_path(s).exists():
            logger.info("Proactive alerts skipped: not signed in to Google")
            return []
        self._scheduler = BackgroundScheduler()
        jobs = {"event": self.check_events, "email": self.check_email}
        started = []
        for name, enabled in wanted.items():
            if enabled:
                self._scheduler.add_job(
                    self._guard(name, jobs[name]),
                    "interval",
                    minutes=s.alert_poll_minutes,
                    id=name,
                    next_run_time=datetime.now().astimezone() + timedelta(seconds=5),
                )
                started.append(name)
        self._scheduler.start()
        return started

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def _guard(self, name: str, check: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                check()
            except GoogleError as exc:
                logger.warning("Stopping %s alerts: %s", name, exc)
                self._notify(f"I stopped checking {name} alerts. {exc}")
                if self._scheduler is not None:
                    self._scheduler.remove_job(name)
            except Exception as exc:  # noqa: BLE001  (network errors: try again next time)
                logger.warning("%s alert check failed: %s", name, exc)

        return run

    def _notify(self, message: str) -> None:
        try:
            self._alert(message)
        except Exception:
            logger.exception("Alert callback failed")

    def check_events(self, now: datetime | None = None) -> None:
        now = now or datetime.now().astimezone()
        lead = timedelta(minutes=self._settings.alert_event_minutes)
        items = (
            service("calendar", "v3")
            .events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=(now + lead).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=10,
            )
            .execute()
            .get("items", [])
        )
        for event in items:
            start = event.get("start", {}).get("dateTime")
            key = f"{event['id']}@{start}"
            if start is None or key in self._seen_events:
                continue
            self._seen_events.add(key)
            minutes = max(0, round((datetime.fromisoformat(start) - now).total_seconds() / 60))
            self._notify(f"{event.get('summary', 'An event')} starts in {minutes} minutes.")

    def check_email(self) -> None:
        gmail = service("gmail", "v1")
        label = self._settings.alert_email_label
        listing = (
            gmail.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD", label], maxResults=10)
            .execute()
        )
        ids = {m["id"] for m in listing.get("messages", [])}
        if self._seen_mail is None:  # first poll: existing mail is not "new"
            self._seen_mail = ids
            return
        for message_id in ids - self._seen_mail:
            message = (
                gmail.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject"],
                )
                .execute()
            )
            sender = header(message, "From").split("<")[0].strip() or "someone"
            self._notify(f"New important email from {sender}: {header(message, 'Subject')}")
        self._seen_mail |= ids
