"""Goc calistirici. Laravel'in `migrations` tablosu gibi uygulanan gocleri kaydeder;
her goc bir kez, listedeki sirayla calisir. Yeni goc: modul ekle, MIGRATIONS'a kaydet."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Callable

from . import (m0001_rbac_tablolari, m0002_envanter_sahiplik, m0003_sifre_sifirlama_ve_jwt,
               m0004_yonetim, m0005_kuyruk_bildirim, m0006_envanter_islemleri,
               m0007_faaliyet_belgeleri_acik_riza)

MIGRATIONS: list[tuple[str, Callable[[sqlite3.Connection], None]]] = [
    ("0001_rbac_tablolari", m0001_rbac_tablolari.up),
    ("0002_envanter_sahiplik", m0002_envanter_sahiplik.up),
    ("0003_sifre_sifirlama_ve_jwt", m0003_sifre_sifirlama_ve_jwt.up),
    ("0004_yonetim", m0004_yonetim.up),
    ("0005_kuyruk_bildirim", m0005_kuyruk_bildirim.up),
    ("0006_envanter_islemleri", m0006_envanter_islemleri.up),
    ("0007_faaliyet_belgeleri_acik_riza", m0007_faaliyet_belgeleri_acik_riza.up),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def applied(conn: sqlite3.Connection) -> set[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS migrations ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, migration TEXT NOT NULL UNIQUE,"
        " batch INTEGER NOT NULL, migrated_at TEXT NOT NULL)")
    return {r[0] for r in conn.execute("SELECT migration FROM migrations")}


def migrate(conn: sqlite3.Connection) -> list[str]:
    done = applied(conn)
    batch = conn.execute("SELECT COALESCE(MAX(batch), 0) FROM migrations").fetchone()[0] + 1
    yeni: list[str] = []
    for ad, up in MIGRATIONS:
        if ad in done:
            continue
        up(conn)
        conn.execute("INSERT INTO migrations (migration, batch, migrated_at) VALUES (?, ?, ?)",
                     (ad, batch, _now()))
        conn.commit()
        yeni.append(ad)
    return yeni
