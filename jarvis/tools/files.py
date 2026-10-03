"""File tools, limited to a set of allowed folders."""

import os
import shutil
from pathlib import Path

from send2trash import send2trash

from jarvis.core.config import get_settings
from jarvis.tools.registry import RISKY, tool

MAX_RESULTS = 10


def allowed_roots() -> list[Path]:
    configured = get_settings().file_roots
    if configured:
        return [Path(p).expanduser().resolve() for p in configured]
    home = Path.home()
    names = ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")
    return [(home / n).resolve() for n in names if (home / n).is_dir()]


def _inside(path: Path, roots: list[Path]) -> bool:
    return any(path == r or r in path.parents for r in roots)


def resolve_path(raw: str) -> Path:
    """Resolve a user path and make sure it stays inside the allowed folders.

    Relative paths (including bare folder names like 'Desktop') are tried against each
    allowed root and its parent; a new relative path lands in the first root.
    """
    roots = allowed_roots()
    path = Path(os.path.expandvars(raw)).expanduser()
    if not path.is_absolute():
        for root in roots:
            for candidate in (root / path, root.parent / path):
                if candidate.exists() and _inside(candidate.resolve(), roots):
                    return candidate.resolve()
        path = (roots[0] if roots else Path.home()) / path
    resolved = path.resolve()
    if not _inside(resolved, roots):
        raise ValueError(f"'{raw}' is outside the folders Jarvis may use")
    return resolved


@tool()
def search_files(query: str, folder: str = "") -> str:
    """Find files by (part of) their name in the user's folders.

    Args:
        query: Part of the file name, case-insensitive.
        folder: Optional folder to search in, e.g. Documents. Empty searches all user folders.
    """
    roots = [resolve_path(folder)] if folder else allowed_roots()
    needle = query.lower()
    found: list[Path] = []
    for root in roots:
        for dirpath, _dirs, filenames in os.walk(root):
            found += [Path(dirpath) / f for f in filenames if needle in f.lower()]
            if len(found) >= MAX_RESULTS:
                break
        if len(found) >= MAX_RESULTS:
            break
    if not found:
        return f"No files matching '{query}' were found."
    return "\n".join(str(p) for p in found[:MAX_RESULTS])


@tool()
def open_file(path: str) -> str:
    """Open a file with its default application.

    Args:
        path: Full path of the file, or a name relative to the user's folders.
    """
    target = resolve_path(path)
    if not target.is_file():
        return f"Error: '{path}' is not an existing file."
    os.startfile(target)
    return f"Opened {target}."


@tool()
def create_file(path: str, content: str = "") -> str:
    """Create a new text file. Never overwrites an existing file.

    Args:
        path: Full path of the new file, or a name relative to the user's folders.
        content: Text to write into the file.
    """
    target = resolve_path(path)
    if target.exists():
        return f"Error: {target} already exists; it was not overwritten."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Created {target}."


@tool()
def write_note(text: str, name: str = "note") -> str:
    """Write text into a new .txt file and open it in Notepad. Use this whenever the user
    wants something written or typed into a note, document or Notepad.

    Args:
        text: The exact text to put in the note, and nothing else.
        name: Short file name without extension, e.g. "shopping list".
    """
    stem = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "note"
    target = resolve_path(f"{stem}.txt")
    number = 2
    while target.exists():  # never overwrite: shopping list 2.txt, 3.txt, ...
        target = resolve_path(f"{stem} {number}.txt")
        number += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    os.startfile(target)
    return f"Wrote the note to {target} and opened it."


@tool()
def move_file(source: str, destination: str) -> str:
    """Move or rename a file or folder. Never overwrites an existing file.

    Args:
        source: Current path of the file.
        destination: New path, or an existing folder to move it into.
    """
    src = resolve_path(source)
    if not src.exists():
        return f"Error: '{source}' does not exist."
    dest = resolve_path(destination)
    if dest.is_dir():
        dest = dest / src.name
    if dest.exists():
        return f"Error: {dest} already exists; nothing was moved."
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return f"Moved to {dest}."


@tool(risk=RISKY)
def delete_file(path: str) -> str:
    """Delete a file or folder by sending it to the Recycle Bin. Asks the user first.

    Args:
        path: Full path of the file, or a name relative to the user's folders.
    """
    target = resolve_path(path)
    if not target.exists():
        return f"Error: '{path}' does not exist."
    send2trash(str(target))
    return f"Moved {target} to the Recycle Bin."
