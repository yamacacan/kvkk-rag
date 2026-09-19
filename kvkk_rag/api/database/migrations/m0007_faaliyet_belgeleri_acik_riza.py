"""Faaliyet belgeleri (envanter degisince otomatik yenilenen faaliyet bazli belgeler:
Aydinlatma Metni, Acik Riza Beyani) ve Acik Riza kayitlari (ilgili kisilerin verdigi /
geri cektigi rizalar; consents modulu, kapsam katmanina tabi)."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS faaliyet_belgeleri (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    faaliyet     TEXT NOT NULL,
    sablon       TEXT NOT NULL,                    -- aydinlatma | acik_riza
    birim        TEXT,
    durum        TEXT NOT NULL DEFAULT 'kuyrukta', -- kuyrukta | uretiliyor | guncel | eski | hata
    parmak_izi   TEXT,                             -- envanter olgulari + kurum profili ozeti (degisim tespiti)
    ad           TEXT,
    dosya        TEXT,
    boyut        INTEGER,
    satir        INTEGER,
    kalan        TEXT,                             -- JSON: bos kalan alanlar
    hata         TEXT,
    son_uretim   TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (faaliyet, sablon)
);
CREATE INDEX IF NOT EXISTS idx_faalbelge_durum ON faaliyet_belgeleri(durum);

CREATE TABLE IF NOT EXISTS consents (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    faaliyet           TEXT NOT NULL,              -- riza verilen faaliyet (Acik Riza Beyani)
    birim              TEXT,                       -- faaliyetin birimi (department kapsami)
    tc_kimlik          TEXT NOT NULL,
    ad                 TEXT NOT NULL,
    soyad              TEXT NOT NULL,
    durum              TEXT NOT NULL,              -- onaylandi | onaylanmadi | geri_cekildi
    onay_tarihi        TEXT,
    geri_cekme_tarihi  TEXT,
    onay_yontemi       TEXT,                       -- islak_imza | elektronik | eposta | sms | sozlu | diger
    notlar             TEXT,
    created_by         INTEGER,
    updated_by         INTEGER,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consents_faaliyet ON consents(faaliyet);
CREATE INDEX IF NOT EXISTS idx_consents_tc ON consents(tc_kimlik);
CREATE INDEX IF NOT EXISTS idx_consents_durum ON consents(durum);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
    conn.commit()
