# Kurum profili kalici deposu. Bir kez kaydedilir, tum belgelerde kullanilir.
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS kurum_profili (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    veri       TEXT NOT NULL,
    guncelleme TEXT NOT NULL
);
"""

ALANLAR = ("kurum", "adres", "web_adres", "faaliyet",
           "veri_isleyen", "sozlesme_adi", "sozlesme_tarihi", "protokol_tarihi")


def connect() -> sqlite3.Connection:
    settings.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get(conn: sqlite3.Connection) -> dict[str, Any]:
    r = conn.execute("SELECT veri, guncelleme FROM kurum_profili WHERE id = 1").fetchone()
    if not r:
        return {a: "" for a in ALANLAR}
    veri = json.loads(r["veri"])
    return {**{a: "" for a in ALANLAR}, **veri, "guncelleme": r["guncelleme"]}


def save(conn: sqlite3.Connection, veri: dict[str, Any]) -> dict[str, Any]:
    temiz = {a: str(veri.get(a) or "").strip() for a in ALANLAR}
    zaman = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO kurum_profili (id, veri, guncelleme) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET veri = excluded.veri, guncelleme = excluded.guncelleme",
        (json.dumps(temiz, ensure_ascii=False), zaman))
    conn.commit()
    return {**temiz, "guncelleme": zaman}
