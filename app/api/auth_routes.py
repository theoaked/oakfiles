from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from app.models import LoginRequest
from app.auth.hashing import verify_password
from app.auth.sessions import create_session, delete_session
from app.auth.middleware import _client_ip
from app.core.audit import log_event

router = APIRouter()


@router.post("/login")
async def login(request: Request):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
    else:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

    db = request.app.state.db
    ip = _client_ip(request)

    row = db.execute(
        "SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if row is None or not row["is_active"] or not verify_password(password, row["password_hash"]):
        log_event(db, username or "(unknown)", ip, "login_failure", {"reason": "invalid_credentials"})
        # Same message regardless of whether user exists
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, csrf = create_session(db, row["id"], ip)
    log_event(db, row["username"], ip, "login_success", {})

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        "csrf_token",
        csrf,
        httponly=False,
        samesite="strict",
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    db = request.app.state.db
    ip = _client_ip(request)

    if token:
        user = getattr(request.state, "user", None)
        username = user["username"] if user else "(unknown)"
        delete_session(db, token)
        log_event(db, username, ip, "logout", {})

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token")
    response.delete_cookie("csrf_token")
    return response
