# Bilgi grafigi semasi. Ayni SQLite dosyasinda yasar (chunks tablolariyla birlikte).
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any, Iterable

from ..config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id     TEXT PRIMARY KEY,
    type   TEXT NOT NULL,
    label  TEXT NOT NULL,
    props  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);

CREATE TABLE IF NOT EXISTS edges (
    src    TEXT NOT NULL,
    dst    TEXT NOT NULL,
    type   TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    props  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (src, dst, type)
);
CREATE INDEX IF NOT EXISTS idx_edges_src  ON edges(src, type);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON edges(dst, type);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
"""

# Dugum tipleri
MADDE = "Madde"
MEVZUAT = "Mevzuat"
KARAR = "Karar"
VERI_KATEGORISI = "VeriKategorisi"
HUKUKI_SEBEP = "HukukiSebep"
ISLEME_AMACI = "IslemeAmaci"
KISI_GRUBU = "KisiGrubu"
ALICI_GRUBU = "AliciGrubu"
TEKNIK_TEDBIR = "TeknikTedbir"
IDARI_TEDBIR = "IdariTedbir"
BIRIM = "Birim"
FAALIYET = "Faaliyet"
ENVANTER = "EnvanterSatiri"
BULGU = "Bulgu"

# Kenar tipleri
HAS_PART = "HAS_PART"          # Mevzuat -> Madde
CITES = "CITES"                # Karar -> Madde (regex, confidence tasir)
TANIMLI_MADDE = "TANIMLI_MADDE"  # HukukiSebep -> Madde (deterministik)
OZEL_NITELIKLI = "OZEL_NITELIKLI"  # VeriKategorisi -> Madde 6
AIT_BIRIM = "AIT_BIRIM"
AIT_FAALIYET = "AIT_FAALIYET"
ICERIR = "ICERIR"              # EnvanterSatiri -> VeriKategorisi
DAYANAK = "DAYANAK"            # EnvanterSatiri -> HukukiSebep
AMAC = "AMAC"
ILGILI_KISI = "ILGILI_KISI"
AKTARIR = "AKTARIR"
TEDBIR = "TEDBIR"
BULGU_OF = "BULGU_OF"          # Bulgu -> EnvanterSatiri
IHLAL_MADDE = "IHLAL_MADDE"    # Bulgu -> Madde


def connect(path=None) -> sqlite3.Connection:
    path = path or settings.SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def node_id(ntype: str, key: str) -> str:
    # Uzun anahtarlar kirpilirsa carpisir (25 hukuki sebepten 3'u ayni ilk 80 karakteri
    # paylasiyordu). Kirpma yerine hash eklenir; label tam metni tasir.
    key = str(key).strip()
    if len(key) <= 60:
        return f"{ntype}:{key}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{ntype}:{key[:50]}~{digest}"


def upsert_nodes(conn: sqlite3.Connection, rows: Iterable[tuple[str, str, str, dict]]) -> int:
    data = [(nid, t, label, json.dumps(p, ensure_ascii=False)) for nid, t, label, p in rows]
    conn.executemany("INSERT OR REPLACE INTO nodes VALUES (?,?,?,?)", data)
    return len(data)


def upsert_edges(conn: sqlite3.Connection,
                 rows: Iterable[tuple[str, str, str, float, dict]]) -> int:
    data = [(s, d, t, w, json.dumps(p, ensure_ascii=False)) for s, d, t, w, p in rows]
    conn.executemany("INSERT OR REPLACE INTO edges VALUES (?,?,?,?,?)", data)
    return len(data)


def clear(conn: sqlite3.Connection) -> None:
    conn.executescript("DELETE FROM nodes; DELETE FROM edges;")


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    nodes = dict(conn.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type").fetchall())
    edges = dict(conn.execute("SELECT type, COUNT(*) FROM edges GROUP BY type").fetchall())
    return {"nodes": nodes, "edges": edges,
            "toplam_dugum": sum(nodes.values()), "toplam_kenar": sum(edges.values())}
