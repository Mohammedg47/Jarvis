"""System tray icon: Mute, Roam and Quit. The icon shows the character's current state."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from jarvis.core.events import State
from jarvis.core.personality import PERSONALITIES, PersonalityControl
from jarvis.ui.character import CharacterWindow

ICON_SIZE = 64


@dataclass
class TrayControls:
    """What the tray can change in Jarvis. Without voice there is nothing to mute."""

    is_muted: Callable[[], bool] | None = None
    set_muted: Callable[[bool], None] | None = None
    personality: PersonalityControl | None = None


def emoji_icon(emoji: str) -> QIcon:
    pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setFont(QFont("Segoe UI Emoji", int(ICON_SIZE * 0.5)))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
    painter.end()
    return QIcon(pixmap)


class Tray:
    def __init__(self, app: QApplication, window: CharacterWindow, controls: TrayControls) -> None:
        self._controls = controls
        self.icon = QSystemTrayIcon(emoji_icon(window.emoji(State.IDLE)), app)
        self.icon.setToolTip("Jarvis")
        self.menu = QMenu()

        self.mute = QAction("Mute spoken replies", self.menu, checkable=True)
        self.mute.setEnabled(controls.set_muted is not None)
        self.mute.toggled.connect(self._toggle_mute)
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
        for action in (self.mute, self.roam, self.quit):
            self.menu.addAction(action)
        self.menu.aboutToShow.connect(self._sync)  # /speak may have changed it
        self.icon.setContextMenu(self.menu)
        self._window = window
        window.state_changed.connect(self.show_state)
        window.personality_changed.connect(lambda _: self.show_state(window._state))

    def show(self) -> bool:
        """Show the icon. False if this desktop has no system tray."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        self.icon.show()
        return True

    def show_state(self, state: State) -> None:
        self.icon.setIcon(emoji_icon(self._window.emoji(state)))

    def _sync(self) -> None:
        if self._controls.personality is not None:
            self.personality[self._controls.personality.value].setChecked(True)
        if self._controls.is_muted is not None:
            self.mute.blockSignals(True)
            self.mute.setChecked(self._controls.is_muted())
            self.mute.blockSignals(False)

    def _toggle_mute(self, muted: bool) -> None:
        if self._controls.set_muted is not None:
            self._controls.set_muted(muted)
