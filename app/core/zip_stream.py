import io
import zipfile
from pathlib import Path
from typing import Generator

from fastapi import HTTPException


def total_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def zip_folder_stream(folder: Path) -> Generator[bytes, None, None]:
    """
    Streams a ZIP of folder without writing to disk.
    Yields raw bytes chunks as each file is compressed.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for file_path in sorted(folder.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(folder)
            try:
                zf.write(file_path, arcname)
            except (PermissionError, OSError):
                continue

            chunk = buf.getvalue()
            if chunk:
                yield chunk
            buf.seek(0)
            buf.truncate(0)

    # Flush the ZIP central directory written when the context manager closes
    final = buf.getvalue()
    if final:
        yield final


def check_zip_size(folder: Path, max_mb: int) -> None:
    size_bytes = total_size(folder)
    if size_bytes > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Folder is too large to ZIP ({size_bytes // (1024*1024)} MB > {max_mb} MB limit)",
        )
