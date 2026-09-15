"""SQLite FTS5 leksik indeks (BM25 tarafi).

Neden FTS5: kalici + artimli, metadata JOIN'i ayni dosyada, graf tablolariyla
(Faz 2) ayni veritabaninda yasar. rank_bm25 her acilista bellege yeniden kurulur
ve metadata filtresiyle birlesmez.

FTS5 Turkce kok bulmaz; bu yuzden text_norm (tr-casefold) sutunu indekslenir.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from ..config import settings
from ..ingest.models import normalize_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    parent_id       TEXT,
    level           TEXT NOT NULL,
    text            TEXT NOT NULL,
    text_raw        TEXT NOT NULL,
    kaynak_turu     TEXT NOT NULL,
    baglayicilik    TEXT NOT NULL,
    otorite_skoru   INTEGER NOT NULL,
    belge_adi       TEXT,
    url             TEXT,
    local_path      TEXT,
    kategori        TEXT,
    bolum           TEXT,
    madde_no        TEXT,
    madde_basligi   TEXT,
    fikra_no        TEXT,
    karar_no        TEXT,
    karar_tarihi    TEXT,
    konu_ozeti      TEXT,
    madde_atiflari  TEXT,
    kavram_etiketleri TEXT,
    char_len        INTEGER,
    token_len       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_id);
CREATE INDEX IF NOT EXISTS idx_chunks_level  ON chunks(level);
CREATE INDEX IF NOT EXISTS idx_chunks_madde  ON chunks(kaynak_turu, madde_no);
CREATE INDEX IF NOT EXISTS idx_chunks_karar  ON chunks(karar_no);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text_norm,
    chunk_id UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);
"""

LIST_FIELDS = ("madde_atiflari", "kavram_etiketleri")


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or settings.SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _row(c: dict[str, Any]) -> tuple:
    return (
        c["chunk_id"], c["doc_id"], c["parent_id"], c["level"], c["text"], c["text_raw"],
        c["kaynak_turu"], c["baglayicilik"], c["otorite_skoru"], c["belge_adi"], c["url"],
        c["local_path"], c["kategori"], c["bolum"], c["madde_no"], c["madde_basligi"],
        c["fikra_no"], c["karar_no"], c["karar_tarihi"], c["konu_ozeti"],
        json.dumps(c["madde_atiflari"], ensure_ascii=False),
        json.dumps(c["kavram_etiketleri"], ensure_ascii=False),
        c["char_len"], c.get("token_len", 0),
    )


def upsert(conn: sqlite3.Connection, chunks: Iterable[dict[str, Any]]) -> int:
    rows = [_row(c) for c in chunks]
    if not rows:
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO chunks VALUES (" + ",".join("?" * 24) + ")", rows
    )
    ids = [r[0] for r in rows]
    conn.executemany("DELETE FROM chunks_fts WHERE chunk_id = ?", [(i,) for i in ids])
    conn.executemany(
        "INSERT INTO chunks_fts (text_norm, chunk_id) VALUES (?, ?)",
        [(normalize_text(r[4]), r[0]) for r in rows],  # r[4]=text (provenans oneki dahil)
    )
    conn.commit()
    return len(rows)


def search(conn: sqlite3.Connection, query: str, limit: int = 40,
           level: str = "child", baglayicilik: str | None = None) -> list[dict[str, Any]]:
    """BM25 arama. FTS5 sorgu sozdizimi kacisi icin terimler tirnaklanir."""
    terms = [t for t in normalize_text(query).split() if len(t) > 1]
    if not terms:
        return []
    fts_query = " OR ".join(f'"{t}"' for t in terms)

    extra, params = "", [fts_query, level]
    if baglayicilik:
        extra = " AND c.baglayicilik LIKE ?"
        params.append(f"{baglayicilik}%")
    params.append(limit)

    sql = f"""
        SELECT c.*, bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
        WHERE chunks_fts MATCH ? AND c.level = ?{extra}
        ORDER BY score
        LIMIT ?
    """
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_by_id(conn: sqlite3.Connection, chunk_ids: list[str]) -> dict[str, dict]:
    if not chunk_ids:
        return {}
    q = ",".join("?" * len(chunk_ids))
    rows = conn.execute(f"SELECT * FROM chunks WHERE chunk_id IN ({q})", chunk_ids).fetchall()
    return {r["chunk_id"]: dict(r) for r in rows}


def count(conn: sqlite3.Connection) -> dict[str, int]:
    out = {}
    for level in ("parent", "child"):
        out[level] = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE level = ?", (level,)
        ).fetchone()[0]
    return out
