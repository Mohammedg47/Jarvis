"""System control tools: volume, mute, lock and shutdown."""

import ctypes
import subprocess

from jarvis.tools.registry import RISKY, tool


def _volume_endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


@tool()
def set_volume(percent: int) -> str:
    """Set the system volume.

    Args:
        percent: Volume from 0 to 100.
    """
    level = max(0, min(100, percent))
    _volume_endpoint().SetMasterVolumeLevelScalar(level / 100, None)
    return f"Volume set to {level}%."


@tool()
def mute(muted: bool = True) -> str:
    """Mute or unmute the system sound.

    Args:
        muted: True to mute, False to unmute.
    """
    _volume_endpoint().SetMute(1 if muted else 0, None)
    return "Muted." if muted else "Unmuted."


@tool()
def lock_screen() -> str:
    """Lock the screen (Windows lock screen)."""
    if not ctypes.windll.user32.LockWorkStation():
        return "Error: could not lock the screen."
    return "Screen locked."


@tool(risk=RISKY)
def shutdown() -> str:
    """Shut down the computer in 30 seconds. Asks the user first."""
    subprocess.run(["shutdown", "/s", "/t", "30"], check=True)
    return "The computer will shut down in 30 seconds."
