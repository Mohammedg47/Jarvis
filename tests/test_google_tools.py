import base64
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from jarvis.core.config import Settings
from jarvis.google import alerts, service
from jarvis.google.alerts import AlertPoller
from jarvis.tools import RISKY, SAFE, default_registry, gmail
from jarvis.tools import calendar as cal


@pytest.fixture
def fake(monkeypatch):
    """Replace the Google client with a MagicMock; returns it."""
    client = MagicMock()
    monkeypatch.setattr(cal, "service", lambda *a: client)
    monkeypatch.setattr(gmail, "service", lambda *a: client)
    monkeypatch.setattr(alerts, "service", lambda *a: client)
    return client


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_risk_levels():
    for name in ("create_event", "edit_event", "send_email"):
        assert default_registry.get(name).risk == RISKY
    for name in ("list_events", "read_emails", "summarize_email", "draft_email"):
        assert default_registry.get(name).risk == SAFE


def test_list_events_formats_timed_and_all_day(fake):
    fake.events().list().execute.return_value = {
        "items": [
            {
                "id": "a1",
                "summary": "Standup",
                "location": "Room 4",
                "start": {"dateTime": "2026-10-05T09:00:00+00:00"},
                "end": {"dateTime": "2026-10-05T09:30:00+00:00"},
            },
            {
                "id": "b2",
                "summary": "Quiz",
                "start": {"date": "2026-10-08"},
                "end": {"date": "2026-10-09"},
            },
        ]
    }
    out = cal.list_events(days=7)
    assert "[a1]" in out and "Standup" in out and "@ Room 4" in out
    assert "[b2]" in out and "(all day)" in out


def test_list_events_empty_and_bad_date(fake):
    fake.events().list().execute.return_value = {}
    assert cal.list_events() == "No events in that period."
    assert cal.list_events(start_date="tomorrow").startswith("Error")


def test_create_event_sends_start_and_end(fake):
    fake.events().insert().execute.return_value = {
        "id": "n1",
        "summary": "Dentist",
        "start": {"dateTime": "2026-12-01T14:00:00+00:00"},
        "end": {"dateTime": "2026-12-01T15:00:00+00:00"},
    }
    assert cal.create_event("Dentist", "2026-12-01 14:00", 45).startswith("Created:")
    body = fake.events().insert.call_args.kwargs["body"]
    start = datetime.fromisoformat(body["start"]["dateTime"])
    assert datetime.fromisoformat(body["end"]["dateTime"]) - start == timedelta(minutes=45)
    assert cal.create_event("x", "nonsense").startswith("Error")


def test_edit_event_keeps_length_and_refuses_all_day(fake):
    fake.events().get().execute.return_value = {
        "id": "e1",
        "summary": "Old",
        "start": {"dateTime": "2026-12-01T10:00:00+00:00"},
        "end": {"dateTime": "2026-12-01T11:30:00+00:00"},
    }
    fake.events().update().execute.return_value = {
        "id": "e1",
        "summary": "New",
        "start": {"dateTime": "2026-12-02T10:00:00+00:00"},
        "end": {"dateTime": "2026-12-02T11:30:00+00:00"},
    }
    assert cal.edit_event("e1", title="New", start="2026-12-02 10:00").startswith("Updated:")
    body = fake.events().update.call_args.kwargs["body"]
    s, e = (datetime.fromisoformat(body[k]["dateTime"]) for k in ("start", "end"))
    assert body["summary"] == "New" and e - s == timedelta(minutes=90)

    fake.events().get().execute.return_value = {"id": "d", "start": {"date": "2026-12-01"}}
    assert "all-day" in cal.edit_event("d", title="x")


def test_read_and_summarize_email(fake):
    msg = {
        "id": "m1",
        "labelIds": ["UNREAD"],
        "snippet": "Don&#39;t miss \u200b this",
        "payload": {
            "headers": [
                {"name": "From", "value": "Ann <ann@x.com>"},
                {"name": "Subject", "value": "Lunch"},
                {"name": "Date", "value": "Mon"},
            ],
            "parts": [{"mimeType": "text/plain", "body": {"data": b64("See you at noon.")}}],
        },
    }
    fake.users().messages().list().execute.return_value = {"messages": [{"id": "m1"}]}
    fake.users().messages().get().execute.return_value = msg
    out = gmail.read_emails()
    assert "[m1] UNREAD" in out and "Subject: Lunch" in out and "Don't miss this" in out
    summary = gmail.summarize_email("m1")
    assert "From: Ann" in summary and "See you at noon." in summary


def test_extract_body_strips_html():
    html = "<style>p{}</style><p>Hello&nbsp;<b>there</b></p>"
    body = gmail.extract_body({"mimeType": "text/html", "body": {"data": b64(html)}})
    assert body.startswith("Hello") and "<" not in body


def test_draft_and_send_validate_address_and_build_message(fake):
    assert gmail.send_email("not-an-address", "s", "b").startswith("Error")
    assert gmail.draft_email("a@x.com, b@y.com", "s", "b").startswith("Error")
    fake.users().drafts().create().execute.return_value = {"id": "d9"}
    assert "d9" in gmail.draft_email("a@x.com", "Hi", "Body text")
    raw = fake.users().drafts().create.call_args.kwargs["body"]["message"]["raw"]
    decoded = base64.urlsafe_b64decode(raw).decode()
    assert "To: a@x.com" in decoded and "Subject: Hi" in decoded and "Body text" in decoded
    assert gmail.send_email("a@x.com", "Hi", "Body").startswith("Email sent")
    fake.users().messages().send.assert_called_once()


def test_tools_report_google_errors_as_text(monkeypatch):
    def broken(*a):
        raise service.GoogleError("Google login has expired.")

    monkeypatch.setattr(cal, "service", broken)
    assert cal.list_events() == "Error: Google login has expired."


def test_event_alert_fires_once(fake):
    sent: list[str] = []
    poller = AlertPoller(Settings(), sent.append)
    now = datetime.now().astimezone()
    soon = (now + timedelta(minutes=8)).isoformat()
    fake.events().list().execute.return_value = {
        "items": [{"id": "e", "summary": "Call", "start": {"dateTime": soon}}]
    }
    poller.check_events(now)
    poller.check_events(now)
    assert sent == ["Call starts in 8 minutes."]


def test_email_alert_skips_existing_then_announces_new(fake):
    sent: list[str] = []
    poller = AlertPoller(Settings(), sent.append)
    listing = fake.users().messages().list().execute
    listing.return_value = {"messages": [{"id": "old"}]}
    poller.check_email()
    assert sent == []
    listing.return_value = {"messages": [{"id": "old"}, {"id": "new"}]}
    fake.users().messages().get().execute.return_value = {
        "payload": {
            "headers": [
                {"name": "From", "value": "Boss <boss@x.com>"},
                {"name": "Subject", "value": "Urgent"},
            ]
        }
    }
    poller.check_email()
    poller.check_email()
    assert sent == ["New important email from Boss: Urgent"]


def test_disabled_alerts_start_no_polling(tmp_path):
    settings = Settings(data_dir=tmp_path, alert_events=False, alert_important_email=False)
    assert AlertPoller(settings, print).start() == []


def test_only_enabled_alert_polls(tmp_path):
    (tmp_path / "token.json").write_text("{}")
    poller = AlertPoller(Settings(data_dir=tmp_path, alert_events=False), print)
    try:
        assert poller.start() == ["email"]
    finally:
        poller.stop()
