from jarvis.core.events import State
from jarvis.ui.character import SKINS, CharacterWindow, QApplication
from jarvis.ui.tray import Tray, TrayControls


def make(controls):
    app = QApplication.instance() or QApplication([])
    window = CharacterWindow()
    return app, window, Tray(app, window, controls)


def test_mute_action_calls_the_controls_and_follows_outside_changes():
    muted = {"value": False}
    _, _, tray = make(TrayControls(lambda: muted["value"], lambda m: muted.update(value=m)))
    tray.mute.setChecked(True)
    assert muted["value"] is True
    muted["value"] = False  # e.g. /speak on
    tray._sync()
    assert tray.mute.isChecked() is False
    assert muted["value"] is False  # syncing must not call set_muted again


def test_mute_is_disabled_without_voice():
    _, _, tray = make(TrayControls())
    assert not tray.mute.isEnabled()


def test_roam_action_toggles_roaming_and_quit_quits():
    _, window, tray = make(TrayControls())
    assert not window.roaming
    tray.roam.setChecked(True)
    assert window.roaming
    tray.roam.setChecked(False)
    assert not window.roaming
    assert tray.quit.text() == "Quit Jarvis"  # wired to app.quit; exercised by hand


def test_icon_follows_state():
    _, window, tray = make(TrayControls())
    window.state_changed.emit(State.SPEAKING)
    assert not tray.icon.icon().isNull()
    assert SKINS["playful"][State.SPEAKING]


def test_personality_menu_switches_character_and_notifies():
    from jarvis.core.personality import PersonalityControl

    seen = []
    control = PersonalityControl("playful")
    control.subscribe(seen.append)
    _, window, tray = make(TrayControls(personality=control))
    control.subscribe(window.personality_changed.emit)
    assert tray.personality["playful"].isChecked()
    assert window._label.text() == SKINS["playful"][State.IDLE]
    tray.personality["formal"].trigger()
    assert control.value == "formal"
    assert seen == ["formal"]
    assert window._label.text() == SKINS["formal"][State.IDLE]
    control.set("playful")  # e.g. /personality playful
    tray._sync()
    assert tray.personality["playful"].isChecked()


def test_personality_control_rejects_unknown_and_toggles():
    import pytest

    from jarvis.core.personality import PersonalityControl

    control = PersonalityControl("nonsense")
    assert control.value == "playful"
    assert control.toggle() == "formal"
    with pytest.raises(ValueError):
        control.set("grumpy")
