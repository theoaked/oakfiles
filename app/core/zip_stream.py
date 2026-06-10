import zipfile
from collections import deque
from pathlib import Path
from typing import Generator

from fastapi import HTTPException

_CHUNK_SIZE = 1024 * 1024


def total_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


class _StreamSink:
    """Unseekable write-only sink: collects ZipFile output for the generator.

    Being unseekable makes ZipFile use data descriptors and track member
    offsets via tell(), which must reflect the total bytes ever written —
    truncating/rewinding a real buffer would corrupt the central directory.
    """

    def __init__(self) -> None:
        self._chunks: deque[bytes] = deque()
        self._pos = 0

    def write(self, data) -> int:
        data = bytes(data)
        if data:
            self._chunks.append(data)
            self._pos += len(data)
        return len(data)

    def tell(self) -> int:
        return self._pos

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        pass

    def drain(self) -> Generator[bytes, None, None]:
        while self._chunks:
            yield self._chunks.popleft()


def zip_folder_stream(folder: Path) -> Generator[bytes, None, None]:
    """
    Streams a ZIP of folder without writing to disk and with constant memory:
    each file is read and compressed in 1 MB chunks, yielded as produced.
    ZIP64 is enabled, so archives and members above 4 GB are supported.
    """
    sink = _StreamSink()

    with zipfile.ZipFile(sink, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for file_path in sorted(folder.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = str(file_path.relative_to(folder))
            try:
                src = open(file_path, "rb")
            except (PermissionError, OSError):
                continue

            with src:
                zinfo = zipfile.ZipInfo.from_file(file_path, arcname)
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                with zf.open(zinfo, "w") as dst:
                    while True:
                        data = src.read(_CHUNK_SIZE)
                        if not data:
                            break
                        dst.write(data)
                        yield from sink.drain()
            yield from sink.drain()

    # Central directory written when the ZipFile context closes
    yield from sink.drain()


def check_zip_size(folder: Path, max_mb: int) -> None:
    size_bytes = total_size(folder)
    if size_bytes > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Folder is too large to ZIP ({size_bytes // (1024*1024)} MB > {max_mb} MB limit)",
        )
