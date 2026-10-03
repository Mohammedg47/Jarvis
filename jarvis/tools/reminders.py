"""Timers and clock-time reminders. Timers live in memory; reminders are saved in SQLite so
they survive a restart. Alerts go to the `alert` callback given to `start()`."""

import logging
from collections.abc import Callable
from datetime import datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from jarvis.memory import MemoryStore
from jarvis.tools.registry import tool

logger = logging.getLogger("jarvis.reminders")

_scheduler: BackgroundScheduler | None = None
_store: MemoryStore | None = None
_alert: Callable[[str], None] = print


def start(store: MemoryStore | None, alert: Callable[[str], None]) -> None:
    """Start the scheduler and re-arm saved reminders. Overdue ones fire right away."""
    global _scheduler, _store, _alert
    stop()
    _store, _alert = store, alert
    _scheduler = BackgroundScheduler()
    _scheduler.start()
    if store is not None:
        for reminder_id, message, due_at in store.pending_reminders():
            _schedule(message, due_at, reminder_id)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def _schedule(message: str, due_at: datetime, reminder_id: int | None) -> None:
    # misfire_grace_time=None: a reminder missed while Jarvis was closed still fires.
    _scheduler.add_job(
        _fire, "date", run_date=due_at, args=[message, reminder_id], misfire_grace_time=None
    )


def _fire(message: str, reminder_id: int | None) -> None:
    if reminder_id is not None and _store is not None:
        _store.finish_reminder(reminder_id)
    logger.info("Alert: %s", message)
    try:
        _alert(message)
    except Exception:
        logger.exception("Alert callback failed")


def parse_when(when: str, now: datetime | None = None) -> datetime:
    """Parse "YYYY-MM-DD HH:MM" or "HH:MM" (next occurrence) as local time. Raises ValueError."""
    now = now or datetime.now().astimezone()
    text = when.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).astimezone()
        except ValueError:
            pass
    try:
        t = time.fromisoformat(text)
    except ValueError:
        raise ValueError(f"Could not understand '{when}'. Use 'YYYY-MM-DD HH:MM' or 'HH:MM'.")
    due = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    return due if due > now else due + timedelta(days=1)


@tool()
def set_timer(minutes: float, message: str = "Time is up.") -> str:
    """Start a countdown timer that alerts the user when it ends. Lost if Jarvis is closed; for a clock time use set_reminder.

    Args:
        minutes: How many minutes until the alert, e.g. 0.5 for thirty seconds.
        message: What to say when the timer ends.
    """
    if _scheduler is None:
        return "Error: timers are not available."
    if minutes <= 0:
        return "Error: minutes must be greater than zero."
    _schedule(message, datetime.now().astimezone() + timedelta(minutes=minutes), None)
    return f"Timer set for {minutes:g} minutes."


@tool()
def set_reminder(message: str, when: str) -> str:
    """Remind the user at a clock time. It is saved and still fires after a restart. Call get_time first if you need today's date.

    Args:
        message: What to remind the user about.
        when: Local time as "YYYY-MM-DD HH:MM", or "HH:MM" for the next time that clock time occurs (24-hour).
    """
    if _scheduler is None or _store is None:
        return "Error: reminders are not available."
    try:
        due = parse_when(when)
    except ValueError as exc:
        return f"Error: {exc}"
    if due <= datetime.now().astimezone():
        return "Error: that time has already passed."
    _schedule(message, due, _store.add_reminder(message, due))
    return f"Reminder set for {due.strftime('%A %d %B, %H:%M')}: {message}"
