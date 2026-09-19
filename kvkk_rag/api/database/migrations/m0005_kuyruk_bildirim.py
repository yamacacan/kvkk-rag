"""Kuyruk (jobs), bildirimler (notifications) ve uretilen belgeler (generated_documents).

jobs                : veritabani tabanli is kuyrugu (Laravel `database` queue driver);
                      worker (surec ici thread ya da `queue:work`) buradan is ceker.
notifications       : kullaniciya ozel uygulama ici bildirimler (header zili).
generated_documents : arka planda uretilen uyum belgeleri; dosya diskte, kaydi burada."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    queue         TEXT NOT NULL DEFAULT 'default',
    job           TEXT NOT NULL,                 -- modul.yolu:SinifAdi
    payload       TEXT NOT NULL,                 -- JSON: is ozellikleri
    status        TEXT NOT NULL DEFAULT 'queued',-- queued | running | done | failed
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 1,
    user_id       INTEGER,                       -- isi baslatan kullanici (bildirim/denetim icin)
    error         TEXT,
    available_at  TEXT NOT NULL,
    reserved_at   TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, available_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    type       TEXT NOT NULL,                    -- documents.ready | documents.failed | ...
    level      TEXT NOT NULL DEFAULT 'bilgi',    -- ok | bilgi | uyari | hata
    title      TEXT NOT NULL,
    body       TEXT,
    link       TEXT,                             -- arayuz yolu (ornegin /belgeler)
    data       TEXT,                             -- JSON: ek alanlar (belge id vb.)
    read_at    TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, read_at);

CREATE TABLE IF NOT EXISTS generated_documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    job_id      INTEGER,
    sablon      TEXT NOT NULL,
    sablon_adi  TEXT,
    tur         TEXT NOT NULL DEFAULT 'docx',    -- docx | zip
    durum       TEXT NOT NULL DEFAULT 'kuyrukta',-- kuyrukta | uretiliyor | hazir | hata
    istek       TEXT NOT NULL,                   -- JSON: DocumentRequest
    ad          TEXT,                            -- indirme dosya adi
    dosya       TEXT,                            -- diskteki yol
    boyut       INTEGER,
    kalan       TEXT,                            -- JSON: doldurulmayan alanlar
    yapay_zeka  TEXT,                            -- JSON: yapay zeka ile yazilan bolumler
    uretilen    INTEGER,                         -- zip icindeki belge sayisi
    hatalar     TEXT,                            -- JSON: atlanan faaliyetler
    hata        TEXT,
    satir       INTEGER,                         -- belgeye giren envanter satiri
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gendoc_user ON generated_documents(user_id, created_at);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
    conn.commit()
