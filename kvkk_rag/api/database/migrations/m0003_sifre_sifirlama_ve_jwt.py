"""Sifre sifirlama jetonlari (Laravel password_reset_tokens) ve uygulama anahtarlari
(app_keys: KVKK_JWT_SECRET verilmemisse uretilen JWT gizli anahtari)."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    email      TEXT PRIMARY KEY COLLATE NOCASE,
    token      TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_keys (
    name       TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
