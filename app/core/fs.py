import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import AppConfig
from app.core.paths import get_locked_paths, _is_under

try:
    import magic as _magic
    _HAS_MAGIC = True
except ImportError:
    _HAS_MAGIC = False


@dataclass
class EntryInfo:
    name: str
    is_dir: bool
    size: Optional[int]
    mtime: str
    path: str


@dataclass
class SearchResult:
    name: str
    path: str
    is_dir: bool
    size: Optional[int]
    mtime: str


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_HIDDEN_NAMES = frozenset({
    "desktop.ini", "thumbs.db", "ntldr", "bootmgr", "bootnxt",
    "pagefile.sys", "hiberfil.sys", "swapfile.sys",
    "$recycle.bin", "system volume information", "recycler",
    "$sysreset", "$windows.~bt", "$windows.~ws",
})


def _is_hidden(name: str) -> bool:
    return name.startswith(".") or name.lower() in _HIDDEN_NAMES


def list_directory(path: Path, show_hidden: bool = False) -> list[EntryInfo]:
    entries = []
    try:
        items = list(path.iterdir())
    except PermissionError:
        return []

    if not show_hidden:
        items = [i for i in items if not _is_hidden(i.name)]

    dirs = sorted([i for i in items if i.is_dir()], key=lambda x: x.name.lower())
    files = sorted([i for i in items if i.is_file()], key=lambda x: x.name.lower())

    for item in dirs + files:
        try:
            stat = item.stat()
            size = stat.st_size if item.is_file() else None
            mtime = _fmt_mtime(stat.st_mtime)
        except (PermissionError, OSError):
            size = None
            mtime = ""
        entries.append(
            EntryInfo(
                name=item.name,
                is_dir=item.is_dir(),
                size=size,
                mtime=mtime,
                path=str(item),
            )
        )
    return entries


def search_files(root_path: Path, query: str, config: AppConfig, show_hidden: bool = False) -> list[SearchResult]:
    locked = get_locked_paths()
    results = []
    q = query.lower()

    for item in root_path.rglob("*"):
        if any(_is_under(item, locked_p) for locked_p in locked):
            continue
        if not show_hidden and any(_is_hidden(part) for part in item.parts):
            continue
        if q in item.name.lower():
            try:
                stat = item.stat()
                size = stat.st_size if item.is_file() else None
                mtime = _fmt_mtime(stat.st_mtime)
            except (PermissionError, OSError):
                size = None
                mtime = ""
            results.append(
                SearchResult(
                    name=item.name,
                    path=str(item),
                    is_dir=item.is_dir(),
                    size=size,
                    mtime=mtime,
                )
            )
        if len(results) >= 500:
            break

    return results


def get_file_mimetype(path: Path) -> str:
    if _HAS_MAGIC:
        try:
            return _magic.from_file(str(path), mime=True)
        except Exception:
            pass
    # Fallback: extension-based
    suffix = path.suffix.lower()
    _EXT_MAP = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".bmp": "image/bmp", ".mp4": "video/mp4", ".webm": "video/webm",
        ".ogg": "video/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav",
        ".flac": "audio/flac", ".pdf": "application/pdf",
        ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json",
        ".xml": "application/xml", ".csv": "text/csv", ".yaml": "text/yaml",
        ".yml": "text/yaml", ".py": "text/x-python", ".js": "text/javascript",
        ".ts": "text/typescript", ".html": "text/html", ".css": "text/css",
    }
    return _EXT_MAP.get(suffix, "application/octet-stream")
