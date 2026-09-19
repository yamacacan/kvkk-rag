"""Envantere sahiplik/atama sutunlari: kapsam katmaninin own (created_by),
assigned (sorumlu_id + envanter_denetcileri) ve department (birim) filtreleri bu
sutunlar uzerinden calisir. Log tablosuna islemi yapan kullanici eklenir."""
from __future__ import annotations

import sqlite3

from ....inventory import store as inv_store


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    var = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in var:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(inv_store.SCHEMA)  # envanter tablosu henuz yoksa olusur
    _add_column(conn, "envanter", "created_by", "INTEGER")
    _add_column(conn, "envanter", "sorumlu_id", "INTEGER")
    _add_column(conn, "envanter_log", "kullanici_id", "INTEGER")
    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_env_created_by ON envanter(created_by);
    CREATE INDEX IF NOT EXISTS idx_env_sorumlu ON envanter(sorumlu_id);

    -- assigned kapsami: sorumlu (lider) disinda ekip uyesi/denetci olarak atananlar
    CREATE TABLE IF NOT EXISTS envanter_denetcileri (
        satir_no INTEGER NOT NULL,
        user_id  INTEGER NOT NULL,
        PRIMARY KEY (satir_no, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_env_denetci_user ON envanter_denetcileri(user_id);
    """)
    conn.commit()
