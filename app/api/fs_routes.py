import re
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles

from app.core.paths import resolve_safe_path
from app.core.fs import list_directory, search_files, get_file_mimetype, EntryInfo, SearchResult
from app.core.zip_stream import zip_folder_stream, check_zip_size
from app.core.transcode import is_transcodable, resolve_ffmpeg, transcode_stream
from app.core.audit import log_event
from app.auth.middleware import _client_ip

router = APIRouter(prefix="/api")


def _entry_dict(e: EntryInfo) -> dict:
    return {"name": e.name, "is_dir": e.is_dir, "size": e.size, "mtime": e.mtime, "path": e.path}


def _search_dict(r: SearchResult) -> dict:
    return {"name": r.name, "path": r.path, "is_dir": r.is_dir, "size": r.size, "mtime": r.mtime}


@router.get("/ls")
async def list_dir(request: Request, path: str, show_hidden: bool = False):
    user = request.state.user
    config = request.app.state.config
    safe = resolve_safe_path(path, config)

    if not safe.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not safe.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    visible = show_hidden and user["role"] == "admin"
    entries = list_directory(safe, show_hidden=visible)
    return {"path": str(safe), "entries": [_entry_dict(e) for e in entries]}


@router.get("/search")
async def search(request: Request, q: str, path: str, show_hidden: bool = False):
    if not q or len(q.strip()) < 1:
        raise HTTPException(status_code=400, detail="Search query is required")

    user = request.state.user
    config = request.app.state.config
    safe = resolve_safe_path(path, config)

    if not safe.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    visible = show_hidden and user["role"] == "admin"
    results = search_files(safe, q.strip(), config, show_hidden=visible)
    return {"query": q, "results": [_search_dict(r) for r in results]}


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def parse_range_header(header: str | None, file_size: int):
    """Parse a single HTTP Range header.

    Returns (start, end) inclusive byte offsets, None when the full file
    should be served (no/invalid header), or the string "unsatisfiable".
    Multi-range requests are not supported and fall back to the full file.
    """
    if not header:
        return None
    m = _RANGE_RE.match(header.strip())
    if not m:
        return None
    start_s, end_s = m.groups()
    if not start_s and not end_s:
        return None
    if not start_s:
        # Suffix range: last N bytes
        length = int(end_s)
        if length <= 0 or file_size == 0:
            return "unsatisfiable"
        start = max(file_size - length, 0)
        end = file_size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)
    if start >= file_size or start > end:
        return "unsatisfiable"
    return start, end


async def _range_stream(path: Path, start: int, end: int, chunk_size: int = 1024 * 1024):
    async with aiofiles.open(path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = await f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get("/download")
async def download(request: Request, path: str, inline: bool = False):
    config = request.app.state.config
    db = request.app.state.db
    safe = resolve_safe_path(path, config)

    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not safe.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    size = safe.stat().st_size
    rng = parse_range_header(request.headers.get("range"), size)

    if rng == "unsatisfiable":
        raise HTTPException(
            status_code=416,
            detail="Range not satisfiable",
            headers={"Content-Range": f"bytes */{size}"},
        )

    # Log full downloads and the first chunk of a streamed playback,
    # not every subsequent seek/range request for the same file.
    if rng is None or rng[0] == 0:
        user = request.state.user
        ip = _client_ip(request)
        log_event(db, user["username"], ip, "file_downloaded", {"path": str(safe), "size": size})

    # Inline disposition lets browsers (notably iOS Safari) play media in a
    # <video>/<audio> element instead of forcing a download. Used by previews.
    disposition = "inline" if inline else "attachment"
    mime = get_file_mimetype(safe)
    if rng is None:
        return FileResponse(
            path=str(safe),
            media_type=mime,
            filename=safe.name,
            headers={"Accept-Ranges": "bytes"},
            content_disposition_type=disposition,
        )

    start, end = rng
    return StreamingResponse(
        _range_stream(safe, start, end),
        status_code=206,
        media_type=mime,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(end - start + 1),
            "Content-Disposition": f'{disposition}; filename="{safe.name}"',
        },
    )


@router.get("/stream")
async def stream(request: Request, path: str):
    """Transcode a browser-incompatible video to MP4 and stream it inline.

    Used by the preview player for formats `<video>` cannot decode (AVI, MKV,
    WMV, …). Live transcoding does not support seeking or Range requests.
    """
    config = request.app.state.config
    db = request.app.state.db
    safe = resolve_safe_path(path, config)

    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not safe.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")
    if not config.media.transcode_enabled:
        raise HTTPException(status_code=403, detail="Transcoding is disabled")
    if not is_transcodable(safe):
        raise HTTPException(status_code=415, detail="Format is not transcodable")

    ffmpeg = resolve_ffmpeg(config.media.ffmpeg_path)
    if not ffmpeg:
        raise HTTPException(status_code=503, detail="ffmpeg is not available on the server")

    user = request.state.user
    ip = _client_ip(request)
    log_event(db, user["username"], ip, "file_streamed", {"path": str(safe)})

    return StreamingResponse(
        transcode_stream(safe, ffmpeg),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'inline; filename="{safe.stem}.mp4"',
            "Cache-Control": "no-store",
            "Accept-Ranges": "none",
        },
    )


@router.get("/zip")
async def download_zip(request: Request, path: str):
    config = request.app.state.config
    db = request.app.state.db

    if not config.paths.zip_download_enabled:
        raise HTTPException(status_code=403, detail="ZIP download is disabled")

    safe = resolve_safe_path(path, config)

    if not safe.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not safe.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    check_zip_size(safe, config.paths.zip_max_size_mb)

    user = request.state.user
    ip = _client_ip(request)
    log_event(db, user["username"], ip, "folder_zipped", {"path": str(safe)})

    return StreamingResponse(
        zip_folder_stream(safe),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe.name}.zip"'},
    )
