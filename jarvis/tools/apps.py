"""App tools: open, list and close applications."""

import ctypes
import logging
import os
import subprocess
from ctypes import wintypes
from pathlib import Path

import psutil

from jarvis.core.config import get_settings
from jarvis.tools.registry import RISKY, tool

logger = logging.getLogger("jarvis.tools")

# Friendly name -> something os.startfile can launch (exe on PATH / App Paths, or a URI).
DEFAULT_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "spotify": "spotify.exe",
    "vscode": "code",
}

# Never closed, even if asked: closing these breaks Windows or Jarvis itself.
PROTECTED = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe",
    "lsass.exe", "svchost.exe", "dwm.exe", "explorer.exe", "python.exe", "pythonw.exe",
}  # fmt: skip


def _app_map() -> dict[str, str]:
    extra = {k.lower(): v for k, v in get_settings().apps.items()}
    return {**DEFAULT_APPS, **extra}


def _start_menu_shortcut(name: str) -> Path | None:
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    best: Path | None = None
    for root in roots:
        if not root.is_dir():
            continue
        for lnk in root.rglob("*.lnk"):
            stem = lnk.stem.lower()
            if stem == name:
                return lnk
            if name in stem and (best is None or len(stem) < len(best.stem)):
                best = lnk
    return best


def is_known_app(name: str) -> bool:
    """True if open_app can launch `name` (a mapped name or a Start Menu shortcut)."""
    key = name.strip().lower()
    return key in _app_map() or _start_menu_shortcut(key) is not None


def is_running(name: str) -> bool:
    """True if a process called `name` (with or without .exe) is running."""
    wanted = name.strip().lower()
    wanted = wanted if wanted.endswith(".exe") else wanted + ".exe"
    return any((p.info["name"] or "").lower() == wanted for p in psutil.process_iter(["name"]))


@tool()
def open_app(name: str) -> str:
    """Open (launch) an application on the laptop by its name, e.g. notepad or chrome.

    Args:
        name: The application name as the user said it.
    """
    key = name.strip().lower()
    target = _app_map().get(key)
    if target is None:
        shortcut = _start_menu_shortcut(key)
        if shortcut is None:
            return f"Error: I do not know an app called '{name}'."
        target = str(shortcut)
    try:
        os.startfile(target)
    except OSError as exc:
        return f"Error: could not open '{name}': {exc}"
    return f"Opened {name}."


def _visible_window_pids() -> set[int]:
    """Process ids that own a visible, titled window (what a user calls 'open apps')."""
    user32 = ctypes.windll.user32
    pids: set[int] = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pids.add(pid.value)
        return True

    user32.EnumWindows(visit, 0)
    return pids


@tool()
def list_apps() -> str:
    """List the applications currently running with a visible window."""
    names = set()
    for pid in _visible_window_pids():
        try:
            names.add(psutil.Process(pid).name())
        except psutil.Error:
            continue
    return ", ".join(sorted(names, key=str.lower)) or "No apps with open windows were found."


@tool(risk=RISKY)
def close_app(name: str) -> str:
    """Close a running application by its name, e.g. notepad. Asks the user first.

    Args:
        name: The application or process name, e.g. notepad or notepad.exe.
    """
    wanted = name.strip().lower()
    if not wanted.endswith(".exe"):
        wanted += ".exe"
    if wanted in PROTECTED:
        return f"Error: '{name}' is protected and will not be closed."
    # taskkill without /F asks the app to close, so it can offer to save unsaved work.
    result = subprocess.run(
        ["taskkill", "/IM", wanted], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return f"Error: could not close '{name}'. It may not be running."
    return f"Asked {name} to close."
