import os
import shutil
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from typing import List

from app.auth.middleware import require_admin, _client_ip
from app.core.paths import resolve_safe_path, is_valid_filename
from app.core.fs import get_file_mimetype
from app.core.audit import log_event
from app.models import MkdirRequest, RenameRequest, MoveRequest, DeleteRequest

router = APIRouter(prefix="/api")

_ALLOWED_MIMETYPES: set[str] = set()  # empty = allow all; populate to restrict


def _unique_name(dest_dir: Path, name: str) -> Path:
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    suffix = Path(name).suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


@router.post("/upload")
async def upload(
    request: Request,
    path: str = Form(...),
    conflict: str = Form("keep"),
    files: List[UploadFile] = File(...),
    _admin: dict = Depends(require_admin),
):
    config = request.app.state.config
    db = request.app.state.db
    ip = _client_ip(request)
    user = request.state.user

    dest_dir = resolve_safe_path(path, config)
    if not dest_dir.is_dir():
        raise HTTPException(status_code=400, detail="Destination is not a directory")

    results = []
    for upload_file in files:
        filename = upload_file.filename or "upload"
        if not is_valid_filename(filename):
            results.append({"name": filename, "error": "Invalid filename"})
            continue

        if conflict == "overwrite":
            dest_path = dest_dir / filename
        else:
            dest_path = _unique_name(dest_dir, filename)

        try:
            async with aiofiles.open(dest_path, "wb") as f:
                while chunk := await upload_file.read(1024 * 1024):
                    await f.write(chunk)
        except OSError as e:
            results.append({"name": filename, "error": str(e)})
            continue

        size = dest_path.stat().st_size
        log_event(db, user["username"], ip, "file_uploaded", {"path": str(dest_path), "size": size})
        results.append({"name": dest_path.name, "path": str(dest_path), "size": size})

    return {"uploaded": results}


@router.post("/mkdir")
async def mkdir(request: Request, body: MkdirRequest, _admin: dict = Depends(require_admin)):
    config = request.app.state.config
    db = request.app.state.db
    ip = _client_ip(request)
    user = request.state.user

    parent = resolve_safe_path(body.path, config)
    if not parent.is_dir():
        raise HTTPException(status_code=400, detail="Parent is not a directory")

    if not is_valid_filename(body.name):
        raise HTTPException(status_code=400, detail="Invalid folder name")

    new_dir = parent / body.name
    if new_dir.exists():
        raise HTTPException(status_code=409, detail="A file or folder with that name already exists")

    new_dir.mkdir()
    log_event(db, user["username"], ip, "folder_created", {"path": str(new_dir)})
    return {"ok": True, "path": str(new_dir)}


@router.post("/rename")
async def rename(request: Request, body: RenameRequest, _admin: dict = Depends(require_admin)):
    config = request.app.state.config
    db = request.app.state.db
    ip = _client_ip(request)
    user = request.state.user

    src = resolve_safe_path(body.path, config)
    if not src.exists():
        raise HTTPException(status_code=404, detail="Source not found")

    if not is_valid_filename(body.new_name):
        raise HTTPException(status_code=400, detail="Invalid name")

    dest = src.parent / body.new_name
    if dest.exists():
        raise HTTPException(status_code=409, detail="A file or folder with that name already exists")

    src.rename(dest)
    log_event(db, user["username"], ip, "item_renamed", {"from": str(src), "to": str(dest)})
    return {"ok": True, "path": str(dest)}


@router.post("/move")
async def move(request: Request, body: MoveRequest, _admin: dict = Depends(require_admin)):
    config = request.app.state.config
    db = request.app.state.db
    ip = _client_ip(request)
    user = request.state.user

    dest_dir = resolve_safe_path(body.destination, config)
    if not dest_dir.is_dir():
        raise HTTPException(status_code=400, detail="Destination is not a directory")

    moved = []
    for raw_path in body.paths:
        src = resolve_safe_path(raw_path, config)
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Not found: {raw_path}")

        # Prevent moving a directory into itself
        try:
            dest_dir.relative_to(src)
            raise HTTPException(status_code=400, detail="Cannot move a folder into itself")
        except ValueError:
            pass

        dest = dest_dir / src.name
        if dest.exists():
            raise HTTPException(status_code=409, detail=f"'{src.name}' already exists in destination")

        shutil.move(str(src), str(dest))
        log_event(db, user["username"], ip, "item_moved", {"from": str(src), "to": str(dest)})
        moved.append({"from": str(src), "to": str(dest)})

    return {"ok": True, "moved": moved}


@router.delete("/delete")
async def delete(request: Request, body: DeleteRequest, _admin: dict = Depends(require_admin)):
    config = request.app.state.config
    db = request.app.state.db
    ip = _client_ip(request)
    user = request.state.user

    # Validate all paths before deleting any
    targets = []
    for raw_path in body.paths:
        p = resolve_safe_path(raw_path, config)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Not found: {raw_path}")
        targets.append(p)

    for p in targets:
        if p.is_dir():
            item_count = sum(1 for _ in p.rglob("*"))
            shutil.rmtree(p)
            log_event(db, user["username"], ip, "folder_deleted", {"path": str(p), "item_count": item_count})
        else:
            size = p.stat().st_size
            os.unlink(p)
            log_event(db, user["username"], ip, "file_deleted", {"path": str(p), "size": size})

    return {"ok": True, "deleted": [str(p) for p in targets]}
