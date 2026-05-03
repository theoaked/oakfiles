import secrets
import sqlite3
from typing import Optional


def create_session(db: sqlite3.Connection, user_id: int, ip: Optional[str]) -> tuple[str, str]:
    """Returns (session_token, csrf_token)."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_hex(16)
    db.execute(
        "INSERT INTO sessions (token, user_id, ip_address, csrf_token) VALUES (?, ?, ?, ?)",
        (token, user_id, ip, csrf),
    )
    db.commit()
    return token, csrf


def get_session(db: sqlite3.Connection, token: str) -> Optional[sqlite3.Row]:
    return db.execute(
        """SELECT s.token, s.user_id, s.last_seen, s.csrf_token,
                  u.username, u.role, u.is_active
           FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token = ?""",
        (token,),
    ).fetchone()


def touch_session(db: sqlite3.Connection, token: str) -> None:
    db.execute(
        "UPDATE sessions SET last_seen = strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE token = ?",
        (token,),
    )
    db.commit()


def delete_session(db: sqlite3.Connection, token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))
    db.commit()


def delete_all_sessions_for_user(db: sqlite3.Connection, user_id: int) -> None:
    db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    db.commit()
