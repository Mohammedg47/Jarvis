from pathlib import Path

import pytest

from jarvis.core.config import get_settings
from jarvis.tools import ToolRunner, default_registry, files
from jarvis.tools.apps import list_apps


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Restrict the file tools to a temp folder."""
    monkeypatch.setattr(get_settings(), "file_roots", [tmp_path])
    return tmp_path


def test_phase4_tools_registered_with_expected_risk():
    risky = {"close_app", "delete_file", "shutdown"}
    safe = {
        "open_app", "list_apps", "search_files", "open_file", "create_file",
        "move_file", "set_volume", "mute", "lock_screen",
    }  # fmt: skip
    for name in risky:
        assert default_registry.get(name).risk == "risky"
    for name in safe:
        assert default_registry.get(name).risk == "safe"


def test_list_apps_returns_text():
    assert isinstance(list_apps(), str)


def test_create_search_move(sandbox):
    assert "Created" in files.create_file("notes.txt", "hi")
    assert (sandbox / "notes.txt").read_text(encoding="utf-8") == "hi"
    assert "Error" in files.create_file("notes.txt", "again")  # no overwrite
    assert "notes.txt" in files.search_files("NOTES")
    (sandbox / "sub").mkdir()
    assert "Moved" in files.move_file("notes.txt", "sub")
    assert (sandbox / "sub" / "notes.txt").exists()


def test_paths_outside_roots_are_refused(sandbox):
    outside = Path(sandbox).parent / "evil.txt"
    runner = ToolRunner(default_registry)
    assert "outside" in runner.run("create_file", {"path": str(outside), "content": "x"})
    assert not outside.exists()


def test_delete_requires_confirmation_and_uses_recycle_bin(sandbox, monkeypatch):
    target = sandbox / "bye.txt"
    target.write_text("x")
    trashed = []
    monkeypatch.setattr(files, "send2trash", trashed.append)

    assert "declined" in ToolRunner(default_registry).run("delete_file", {"path": str(target)})
    assert not trashed

    runner = ToolRunner(default_registry, confirm=lambda name, args: True)
    assert "Recycle Bin" in runner.run("delete_file", {"path": str(target)})
    assert trashed == [str(target)]


def test_close_app_refuses_protected_processes():
    runner = ToolRunner(default_registry, confirm=lambda name, args: True)
    assert "protected" in runner.run("close_app", {"name": "explorer"})
