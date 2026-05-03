import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse, Response

from app.auth.sessions import get_session, touch_session, delete_session

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = {"/login", "/static"}
_PUBLIC_PREFIXES = ("/static/",)

_STATE_CHANGING_METHODS = {"POST", "PATCH", "DELETE", "PUT"}


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        token = request.cookies.get("session_token")
        if not token:
            return RedirectResponse("/login", status_code=303)

        db = request.app.state.db
        config = request.app.state.config

        session = get_session(db, token)
        if session is None or not session["is_active"]:
            resp = RedirectResponse("/login", status_code=303)
            resp.delete_cookie("session_token")
            return resp

        timeout = timedelta(minutes=config.server.session_timeout_minutes)
        last_seen = datetime.fromisoformat(session["last_seen"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        if now - last_seen > timeout:
            delete_session(db, token)
            from app.core.audit import log_event
            log_event(db, session["username"], _client_ip(request), "session_expiry", {})
            resp = RedirectResponse("/login", status_code=303)
            resp.delete_cookie("session_token")
            return resp

        touch_session(db, token)

        request.state.user = dict(session)
        request.state.session_token = token

        if request.method in _STATE_CHANGING_METHODS:
            csrf_header = request.headers.get("X-CSRF-Token", "")
            csrf_form = ""
            if not csrf_header and request.headers.get("content-type", "").startswith(
                "application/x-www-form-urlencoded"
            ):
                form = await request.form()
                csrf_form = form.get("_csrf", "")

            submitted = csrf_header or csrf_form
            expected = session["csrf_token"]

            if not hmac.compare_digest(submitted.encode(), expected.encode()):
                raise HTTPException(status_code=403, detail="Invalid CSRF token")

        return await call_next(request)


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def require_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user is None or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
