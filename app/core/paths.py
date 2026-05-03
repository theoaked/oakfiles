import os
import platform
from pathlib import Path

from fastapi import HTTPException

from app.config import AppConfig

_FORBIDDEN_NAME_CHARS = set('\\/:|*?"<>')

_LOCKED_WINDOWS: list[Path] = [
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("C:/ProgramData"),
]

_LOCKED_LINUX: list[Path] = [
    Path("/proc"),
    Path("/sys"),
    Path("/dev"),
    Path("/boot"),
    Path("/etc"),
    Path("/bin"),
    Path("/sbin"),
    Path("/usr/bin"),
    Path("/usr/sbin"),
    Path("/root"),
    Path("/var/run"),
    Path("/run"),
]


def get_locked_paths() -> list[Path]:
    if platform.system() == "Windows":
        locked = [p.resolve() for p in _LOCKED_WINDOWS]
        appdata = Path(os.environ.get("USERPROFILE", "C:/Users/Default")) / "AppData"
        locked.append(appdata.resolve())
        return locked
    return [p.resolve() for p in _LOCKED_LINUX]


def _is_under(path: Path, parent: Path) -> bool:
    """Return True if path == parent or path is inside parent."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_safe_path(raw: str, config: AppConfig) -> Path:
    """
    Resolve raw to an absolute, real path and verify:
      1. It falls under at least one configured root.
      2. It does not fall under any locked system path.
    Raises HTTPException(403) on any violation.
    """
    try:
        resolved = Path(os.path.realpath(raw))
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid path")

    # Must be under a configured root
    if not any(_is_under(resolved, root) for root in config.paths.roots):
        raise HTTPException(status_code=403, detail="Path is outside the allowed directories")

    # Must not be under a locked path
    for locked in get_locked_paths():
        if _is_under(resolved, locked):
            raise HTTPException(status_code=403, detail="Path is in a protected system location")

    return resolved


def is_valid_filename(name: str) -> bool:
    if not name or not name.strip():
        return False
    if any(c in _FORBIDDEN_NAME_CHARS for c in name):
        return False
    if name in (".", ".."):
        return False
    return True
