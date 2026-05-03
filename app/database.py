import sqlite3
import secrets
import string
import logging
from pathlib import Path

from app.config import AppConfig

DB_PATH = Path(__file__).parent.parent / "oakfiles.db"

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('admin','readonly')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_active     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    last_seen   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    ip_address  TEXT,
    csrf_token  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    username   TEXT NOT NULL,
    ip_address TEXT,
    event      TEXT NOT NULL,
    detail     TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_event    ON audit_log(event);
"""

_ALPHABET = string.ascii_letters + string.digits


def _random_password(length: int = 16) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def open_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def bootstrap(db: sqlite3.Connection, config: AppConfig) -> None:
    db.executescript(SCHEMA)
    db.commit()

    row = db.execute(
        "SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1"
    ).fetchone()
    if row[0] == 0:
        from app.auth.hashing import hash_password

        password = _random_password()
        hashed = hash_password(password, config.security.bcrypt_cost)
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            ("admin", hashed),
        )
        db.commit()

        banner = "\n" + "=" * 60
        banner += "\n  FIRST RUN — default admin account created"
        banner += f"\n  Username : admin"
        banner += f"\n  Password : {password}"
        banner += "\n  Change this password after your first login!"
        banner += "\n" + "=" * 60
        print(banner)
        logger.warning("First-run admin account created. Change the password immediately.")
