import json
import sqlite3
from typing import Optional


def log_event(
    db: sqlite3.Connection,
    username: str,
    ip: Optional[str],
    event: str,
    detail: dict,
) -> None:
    db.execute(
        "INSERT INTO audit_log (username, ip_address, event, detail) VALUES (?, ?, ?, ?)",
        (username, ip, event, json.dumps(detail) if detail else None),
    )
    db.commit()
