import sys

from jarvis.core import autostart


def test_enable_and_disable_round_trip(tmp_path):
    assert not autostart.is_enabled(tmp_path)
    autostart.set_enabled(True, tmp_path)
    assert autostart.is_enabled(tmp_path)
    autostart.set_enabled(False, tmp_path)
    assert not autostart.is_enabled(tmp_path)
    autostart.set_enabled(False, tmp_path)  # disabling twice is fine


def test_target_runs_in_the_background_from_source_and_when_packaged(monkeypatch):
    assert autostart.launch_target()[1] == "-m jarvis --background"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "Jarvis.exe")
    assert autostart.launch_target() == ("Jarvis.exe", "--background")
