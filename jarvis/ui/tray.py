"""System tray icon: Help, Mute, Wake word, Roam and Quit. The icon shows the character's state."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from jarvis.core.events import State
from jarvis.core.personality import PERSONALITIES, PersonalityControl
from jarvis.ui.character import CharacterWindow
from jarvis.ui.face import render_icon


@dataclass
class TrayControls:
    """What the tray can change in Jarvis. Without voice there is nothing to mute."""

    is_muted: Callable[[], bool] | None = None
    set_muted: Callable[[bool], None] | None = None
    personality: PersonalityControl | None = None
    on_help: Callable[[], None] | None = None  # "I need help": starts help mode
    on_open_chat: Callable[[], None] | None = None  # show the chat window
    is_wake_on: Callable[[], bool] | None = None
    set_wake: Callable[[bool], bool] | None = None  # returns whether it is on afterwards
    is_autostart: Callable[[], bool] | None = None
    set_autostart: Callable[[bool], None] | None = None


class Tray:
    def __init__(self, app: QApplication, window: CharacterWindow, controls: TrayControls) -> None:
        self._controls = controls
        self.icon = QSystemTrayIcon(render_icon(State.IDLE, window.personality), app)
        self.icon.setToolTip("Jarvis")
        self.menu = QMenu()

        self.open_chat = QAction("Open chat window", self.menu)
        self.open_chat.setEnabled(controls.on_open_chat is not None)
        self.open_chat.triggered.connect(lambda: controls.on_open_chat and controls.on_open_chat())
        self.help = QAction("I need help", self.menu)
        self.help.setEnabled(controls.on_help is not None)
        self.help.triggered.connect(lambda: controls.on_help and controls.on_help())
        self.mute = QAction("Mute spoken replies", self.menu, checkable=True)
        self.mute.setEnabled(controls.set_muted is not None)
        self.mute.toggled.connect(self._toggle_mute)
        self.wake = QAction('Listen for "Hey Jarvis"', self.menu, checkable=True)
        self.wake.setEnabled(controls.set_wake is not None)
        self.wake.toggled.connect(self._toggle_wake)
        self.autostart = QAction("Start with Windows", self.menu, checkable=True)
        self.autostart.setEnabled(controls.set_autostart is not None)
        self.autostart.toggled.connect(lambda on: controls.set_autostart(on))
        self.personality: dict[str, QAction] = {}
        if controls.personality is not None:
            group = QActionGroup(self.menu)
            submenu = self.menu.addMenu("Personality")
            for name in PERSONALITIES:
                action = QAction(name.capitalize(), submenu, checkable=True)
                action.setActionGroup(group)
                action.triggered.connect(lambda _=False, n=name: controls.personality.set(n))
                submenu.addAction(action)
                self.personality[name] = action
            self.personality[controls.personality.value].setChecked(True)
        self.roam = QAction("Wander around the screen", self.menu, checkable=True)
        self.roam.setChecked(window.roaming)
        self.roam.toggled.connect(window.set_roaming)
        self.quit = QAction("Quit Jarvis", self.menu)
        self.quit.triggered.connect(app.quit)
        for action in (
            self.open_chat,
            self.help,
            self.mute,
            self.wake,
            self.roam,
            self.autostart,
            self.quit,
        ):
            self.menu.addAction(action)
        self.menu.aboutToShow.connect(self._sync)  # /speak may have changed it
        self.icon.setContextMenu(self.menu)
        self.icon.activated.connect(self._activated)
        self._window = window
        window.state_changed.connect(self.show_state)
        window.personality_changed.connect(lambda _: self.show_state(window.state))

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """A click on the icon (not the right-click menu) opens the chat window."""
        clicked = (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        )
        if reason in clicked and self._controls.on_open_chat is not None:
            self._controls.on_open_chat()

    def show(self) -> bool:
        """Show the icon. False if this desktop has no system tray."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.icon.show()
        return True

    def show_state(self, state: State) -> None:
        self.icon.setIcon(render_icon(state, self._window.personality))

    def _sync(self) -> None:
        if self._controls.personality is not None:
            self.personality[self._controls.personality.value].setChecked(True)
        if self._controls.is_autostart is not None:
            self.autostart.blockSignals(True)
            self.autostart.setChecked(self._controls.is_autostart())
            self.autostart.blockSignals(False)
        if self._controls.is_wake_on is not None:
            self.wake.blockSignals(True)
            self.wake.setChecked(self._controls.is_wake_on())
            self.wake.blockSignals(False)
        if self._controls.is_muted is not None:
            self.mute.blockSignals(True)
            self.mute.setChecked(self._controls.is_muted())
            self.mute.blockSignals(False)

    def _toggle_wake(self, on: bool) -> None:
        if self._controls.set_wake is not None:
            actual = self._controls.set_wake(on)
            if actual != on:  # it could not start; show the real state
                self.wake.blockSignals(True)
                self.wake.setChecked(actual)
                self.wake.blockSignals(False)

    def _toggle_mute(self, muted: bool) -> None:
        if self._controls.set_muted is not None:
            self._controls.set_muted(muted)
