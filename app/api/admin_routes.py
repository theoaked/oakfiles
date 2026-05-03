import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.hashing import hash_password
from app.auth.middleware import require_admin, _client_ip
from app.auth.sessions import delete_all_sessions_for_user
from app.core.audit import log_event
from app.models import UserCreate, UserPatch

router = APIRouter(prefix="/api")

_VALID_ROLES = {"admin", "readonly"}


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(request: Request, _admin: dict = Depends(require_admin)):
    db = request.app.state.db
    rows = db.execute(
        "SELECT id, username, role, created_at, is_active FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users")
async def create_user(request: Request, body: UserCreate, _admin: dict = Depends(require_admin)):
    db = request.app.state.db
    ip = _client_ip(request)
    actor = request.state.user

    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {_VALID_ROLES}")
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="Username cannot be empty")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = db.execute("SELECT id FROM users WHERE username = ?", (body.username,)).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    config = request.app.state.config
    hashed = hash_password(body.password, config.security.bcrypt_cost)
    db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (body.username.strip(), hashed, body.role),
    )
    db.commit()

    new_row = db.execute(
        "SELECT id, username, role, created_at, is_active FROM users WHERE username = ?",
        (body.username,),
    ).fetchone()

    log_event(db, actor["username"], ip, "user_created", {"new_user": body.username, "role": body.role})
    return dict(new_row)


@router.patch("/users/{user_id}")
async def update_user(
    request: Request, user_id: int, body: UserPatch, _admin: dict = Depends(require_admin)
):
    db = request.app.state.db
    ip = _client_ip(request)
    actor = request.state.user
    config = request.app.state.config

    row = db.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    updates: list[str] = []
    params: list = []
    changed: dict = {}

    if body.username is not None:
        if not body.username.strip():
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        conflict = db.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?", (body.username, user_id)
        ).fetchone()
        if conflict:
            raise HTTPException(status_code=409, detail="Username already taken")
        updates.append("username = ?")
        params.append(body.username.strip())
        changed["username"] = body.username

    if body.password is not None:
        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        updates.append("password_hash = ?")
        params.append(hash_password(body.password, config.security.bcrypt_cost))
        changed["password"] = "(changed)"

    if body.role is not None:
        if body.role not in _VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role")
        updates.append("role = ?")
        params.append(body.role)
        changed["role"] = body.role

    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(body.is_active)
        changed["is_active"] = body.is_active
        if not body.is_active:
            delete_all_sessions_for_user(db, user_id)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    db.commit()

    log_event(db, actor["username"], ip, "user_updated", {"target_user_id": user_id, "changes": changed})

    updated = db.execute(
        "SELECT id, username, role, created_at, is_active FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return dict(updated)


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: int, _admin: dict = Depends(require_admin)):
    db = request.app.state.db
    ip = _client_ip(request)
    actor = request.state.user

    if actor["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    row = db.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    delete_all_sessions_for_user(db, user_id)
    db.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    db.commit()

    log_event(db, actor["username"], ip, "user_deleted", {"target_username": row["username"]})
    return {"ok": True}


# ── Audit Log ──────────────────────────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    request: Request,
    from_dt: Optional[str] = Query(None, alias="from"),
    to_dt: Optional[str] = Query(None, alias="to"),
    event: Optional[str] = None,
    username: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(require_admin),
):
    db = request.app.state.db

    conditions = []
    params: dict = {}

    if from_dt:
        conditions.append("ts >= :from_dt")
        params["from_dt"] = from_dt
    if to_dt:
        conditions.append("ts <= :to_dt")
        params["to_dt"] = to_dt
    if event:
        conditions.append("event = :event")
        params["event"] = event
    if username:
        conditions.append("username = :username")
        params["username"] = username

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params["limit"] = limit
    params["offset"] = offset

    sql = f"SELECT * FROM audit_log {where} ORDER BY ts DESC LIMIT :limit OFFSET :offset"
    rows = db.execute(sql, params).fetchall()

    total_sql = f"SELECT COUNT(*) FROM audit_log {where}"
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    total = db.execute(total_sql, count_params).fetchone()[0]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {**dict(r), "detail": json.loads(r["detail"]) if r["detail"] else None}
            for r in rows
        ],
    }
