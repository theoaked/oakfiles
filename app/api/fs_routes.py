from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import aiofiles

from app.core.paths import resolve_safe_path
from app.core.fs import list_directory, search_files, get_file_mimetype, EntryInfo, SearchResult
from app.core.zip_stream import zip_folder_stream, check_zip_size
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


@router.get("/download")
async def download(request: Request, path: str):
    config = request.app.state.config
    db = request.app.state.db
    safe = resolve_safe_path(path, config)

    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    if not safe.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    user = request.state.user
    ip = _client_ip(request)
    log_event(db, user["username"], ip, "file_downloaded", {"path": str(safe), "size": safe.stat().st_size})

    mime = get_file_mimetype(safe)
    return FileResponse(path=str(safe), media_type=mime, filename=safe.name)


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
