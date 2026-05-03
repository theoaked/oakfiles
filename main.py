import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import load_config
from app.database import open_db, bootstrap
from app.mdns import start_mdns, stop_mdns
from app.auth.middleware import SessionMiddleware
from app.api.auth_routes import router as auth_router
from app.api.fs_routes import router as fs_router
from app.api.file_ops_routes import router as file_ops_router
from app.api.admin_routes import router as admin_router
from app.web.routes import router as web_router

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def setup_logging():
    handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "service.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler, logging.StreamHandler()])


setup_logging()
logger = logging.getLogger(__name__)

config = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = open_db()
    bootstrap(db, config)
    app.state.db = db
    app.state.config = config

    await start_mdns(config)
    logger.info(f"OakFiles started on {config.server.host}:{config.server.port}")

    yield

    await stop_mdns()
    db.close()
    logger.info("OakFiles stopped")


app = FastAPI(title="OakFiles", lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware)

app.include_router(auth_router)
app.include_router(web_router)
app.include_router(fs_router)
app.include_router(file_ops_router)
app.include_router(admin_router)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


if __name__ == "__main__":
    print(f"Starting OakFiles on http://{config.server.host}:{config.server.port}")
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        log_level="info",
    )
