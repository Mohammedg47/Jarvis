"""Google Calendar tools. Creating and editing events are risky and need confirmation."""

from datetime import date, datetime, timedelta

from jarvis.google.service import google_tool, service
from jarvis.tools.registry import RISKY, tool
from jarvis.tools.reminders import parse_when

MAX_EVENTS = 20


def format_event(event: dict) -> str:
    """One line: `[id] Mon 05 Oct 14:00-15:00 Title @ place`."""
    start, end = event.get("start", {}), event.get("end", {})
    if "dateTime" in start:
        s = datetime.fromisoformat(start["dateTime"]).astimezone()
        e = datetime.fromisoformat(end["dateTime"]).astimezone()
        when = f"{s:%a %d %b %H:%M}-{e:%H:%M}"
    else:
        when = f"{date.fromisoformat(start['date']):%a %d %b} (all day)"
    place = f" @ {event['location']}" if event.get("location") else ""
    return f"[{event['id']}] {when} {event.get('summary', '(no title)')}{place}"


@tool()
@google_tool
def list_events(days: int = 1, start_date: str = "") -> str:
    """List Google Calendar events, soonest first. Use it for "what's on today?" or "what's coming up this week?".

    Args:
        days: How many days to cover, starting at start_date (1 = just that day).
        start_date: First day as "YYYY-MM-DD". Empty means today.
    """
    if days < 1:
        return "Error: days must be at least 1."
    try:
        first = date.fromisoformat(start_date) if start_date else datetime.now().astimezone().date()
    except ValueError:
        return "Error: start_date must look like 2026-10-05."
    begin = datetime.combine(first, datetime.min.time()).astimezone()
    end = datetime.combine(first + timedelta(days=days), datetime.min.time()).astimezone()
    result = (
        service("calendar", "v3")
        .events()
        .list(
            calendarId="primary",
            timeMin=begin.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=MAX_EVENTS,
        )
        .execute()
    )
    events = result.get("items", [])
    if not events:
        return "No events in that period."
    return "\n".join(format_event(e) for e in events)


@tool(risk=RISKY)
@google_tool
def create_event(
    title: str, start: str, duration_minutes: int = 60, location: str = "", description: str = ""
) -> str:
    """Create a Google Calendar event. The user must confirm first. Call get_time first if you need today's date.

    Args:
        title: Event title.
        start: Local start time as "YYYY-MM-DD HH:MM" (24-hour).
        duration_minutes: Length in minutes.
        location: Where it takes place (optional).
        description: Extra notes (optional).
    """
    try:
        begin = parse_when(start)
    except ValueError as exc:
        return f"Error: {exc}"
    if duration_minutes < 1:
        return "Error: duration_minutes must be at least 1."
    body = {
        "summary": title,
        "start": {"dateTime": begin.isoformat()},
        "end": {"dateTime": (begin + timedelta(minutes=duration_minutes)).isoformat()},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    event = service("calendar", "v3").events().insert(calendarId="primary", body=body).execute()
    return f"Created: {format_event(event)}"


@tool(risk=RISKY)
@google_tool
def edit_event(
    event_id: str,
    title: str = "",
    start: str = "",
    duration_minutes: int = 0,
    location: str = "",
) -> str:
    """Change an existing Google Calendar event. The user must confirm first. Get the event_id from list_events. Only pass the fields to change.

    Args:
        event_id: The id shown in square brackets by list_events.
        title: New title (empty keeps the current one).
        start: New local start time as "YYYY-MM-DD HH:MM" (empty keeps it). The length stays the same unless duration_minutes is given.
        duration_minutes: New length in minutes (0 keeps it).
        location: New location (empty keeps it).
    """
    events = service("calendar", "v3").events()
    event = events.get(calendarId="primary", eventId=event_id).execute()
    if "dateTime" not in event.get("start", {}):
        return "Error: all-day events cannot be edited by Jarvis."
    old_start = datetime.fromisoformat(event["start"]["dateTime"])
    old_end = datetime.fromisoformat(event["end"]["dateTime"])
    new_start = old_start
    if start:
        try:
            new_start = parse_when(start)
        except ValueError as exc:
            return f"Error: {exc}"
    length = timedelta(minutes=duration_minutes) if duration_minutes > 0 else old_end - old_start
    if title:
        event["summary"] = title
    if location:
        event["location"] = location
    event["start"] = {"dateTime": new_start.isoformat()}
    event["end"] = {"dateTime": (new_start + length).isoformat()}
    updated = events.update(calendarId="primary", eventId=event_id, body=event).execute()
    return f"Updated: {format_event(updated)}"
