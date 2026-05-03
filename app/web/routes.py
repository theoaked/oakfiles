from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

def _filesizeformat(value):
    if value is None:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} PB"


templates = Jinja2Templates(directory=str(Path(__file__).parent.parent.parent / "templates"))
templates.env.filters["filesizeformat"] = _filesizeformat

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("session_token"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/", response_class=HTMLResponse)
async def browser_page(request: Request):
    user = request.state.user
    config = request.app.state.config
    roots = [str(r) for r in config.paths.roots]
    csrf = user["csrf_token"]
    return templates.TemplateResponse(
        "browser.html",
        {
            "request": request,
            "user": user,
            "roots": roots,
            "csrf_token": csrf,
            "zip_enabled": config.paths.zip_download_enabled,
        },
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    user = request.state.user
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=303)
    csrf = user["csrf_token"]
    return templates.TemplateResponse(
        "admin_users.html", {"request": request, "user": user, "csrf_token": csrf}
    )


@router.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit_page(request: Request):
    user = request.state.user
    if user["role"] != "admin":
        return RedirectResponse("/", status_code=303)
    csrf = user["csrf_token"]
    return templates.TemplateResponse(
        "audit_log.html", {"request": request, "user": user, "csrf_token": csrf}
    )
