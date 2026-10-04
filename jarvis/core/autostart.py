"""Start Jarvis when the user signs in to Windows, with a shortcut in the Startup folder.

(A Startup shortcut is what the installer creates too. A Run registry entry written by an
unsigned program is a pattern Windows Defender treats as suspicious.)
"""

import os
import subprocess
import sys
from pathlib import Path

SHORTCUT_NAME = "Jarvis.lnk"


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def launch_target() -> tuple[str, str]:
    """(program, arguments) that start Jarvis quietly in the tray: the packaged exe, or, from a
    source checkout, the venv's pythonw (no console window)."""
    if getattr(sys, "frozen", False):
        return sys.executable, "--background"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return str(interpreter), "-m jarvis --background"


def is_enabled(folder: Path | None = None) -> bool:
    return ((folder or startup_folder()) / SHORTCUT_NAME).exists()


def set_enabled(on: bool, folder: Path | None = None) -> None:
    shortcut = (folder or startup_folder()) / SHORTCUT_NAME
    if not on:
        shortcut.unlink(missing_ok=True)
        return
    program, arguments = launch_target()
    shortcut.parent.mkdir(parents=True, exist_ok=True)

    def quote(text: str) -> str:  # a PowerShell single-quoted string
        return "'" + text.replace("'", "''") + "'"

    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({quote(str(shortcut))});"
        f"$s.TargetPath = {quote(program)}; $s.Arguments = {quote(arguments)};"
        f"$s.WorkingDirectory = {quote(str(Path(program).parent))}; $s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
