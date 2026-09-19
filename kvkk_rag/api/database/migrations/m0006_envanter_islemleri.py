"""Envanter arka plan islemleri: Excel disa aktarim, Excel'den ice aktarim ve vektor
indeksini yeniden kurma kuyrukta calisir; durumu ve ciktisi (dosya) burada tutulur."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS envanter_islemleri (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    job_id      INTEGER,
    tur         TEXT NOT NULL,                   -- disa_aktar | ice_aktar | yeniden_indeksle
    durum       TEXT NOT NULL DEFAULT 'kuyrukta',-- kuyrukta | calisiyor | tamamlandi | hata
    istek       TEXT NOT NULL,                   -- JSON: filtreler / ice aktarim secenekleri
    ad          TEXT,                            -- indirme / yuklenen dosya adi
    dosya       TEXT,                            -- diskteki yol (cikti ya da yuklenen dosya)
    boyut       INTEGER,
    sonuc       TEXT,                            -- JSON: satir sayilari vb.
    hata        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_envislem_user ON envanter_islemleri(user_id, created_at);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
    conn.commit()
