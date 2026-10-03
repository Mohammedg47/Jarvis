import time
from datetime import datetime, timedelta
from pathlib import Path

from jarvis.memory import MemoryStore
from jarvis.tools import reminders, web


def test_parse_when_clock_time_picks_next_occurrence():
    now = datetime(2026, 1, 1, 10, 0).astimezone()
    assert reminders.parse_when("11:30", now).day == 1
    assert reminders.parse_when("09:00", now).day == 2
    assert reminders.parse_when("2026-03-04 08:15", now).month == 3


def test_parse_when_rejects_nonsense():
    try:
        reminders.parse_when("tomorrow-ish")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_timer_fires_alert():
    fired: list[str] = []
    reminders.start(None, fired.append)
    try:
        assert "Timer set" in reminders.set_timer(0.01, "tea")
        time.sleep(1.2)
    finally:
        reminders.stop()
    assert fired == ["tea"]


def test_reminder_survives_restart(tmp_path: Path):
    path = tmp_path / "memory.db"
    store = MemoryStore(path)
    store.add_reminder("call Sam", datetime.now().astimezone() + timedelta(seconds=1))
    store.close()

    fired: list[str] = []
    store = MemoryStore(path)
    reminders.start(store, fired.append)
    try:
        time.sleep(2)
    finally:
        reminders.stop()
    assert fired == ["call Sam"]
    assert store.pending_reminders() == []


def test_set_reminder_rejects_past_time():
    reminders.start(MemoryStore(Path(":memory:")), print)
    try:
        assert "passed" in reminders.set_reminder("x", "2000-01-01 00:00")
    finally:
        reminders.stop()


def test_web_search_formats_results(monkeypatch):
    class FakeDDGS:
        def text(self, query, max_results):
            return [{"title": "T", "href": "http://x", "body": "B"}]

    monkeypatch.setattr(web, "DDGS", FakeDDGS)
    assert web.web_search("q") == "[1] T\nhttp://x\nB"


def test_web_search_reports_failure(monkeypatch):
    class BrokenDDGS:
        def text(self, query, max_results):
            raise RuntimeError("offline")

    monkeypatch.setattr(web, "DDGS", BrokenDDGS)
    assert web.web_search("q").startswith("Error")
