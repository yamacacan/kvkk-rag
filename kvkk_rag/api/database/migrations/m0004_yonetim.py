"""Yonetim paneli: denetim gunlugu (audit_logs) ve departman aciklamasi."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    user_email  TEXT,
    action      TEXT NOT NULL,
    target_type TEXT,
    target_id   TEXT,
    target_label TEXT,
    before      TEXT,
    after       TEXT,
    ip          TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
    var = {r[1] for r in conn.execute("PRAGMA table_info(departments)")}
    if "description" not in var:
        conn.execute("ALTER TABLE departments ADD COLUMN description TEXT")
    conn.commit()
