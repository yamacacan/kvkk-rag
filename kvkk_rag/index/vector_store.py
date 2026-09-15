# LanceDB vektor deposu. Metadata filtresi pushdown + upsert/delete destegi icin secildi.
from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa

from ..config import settings

TABLE = "chunks"

# Yalnizca child gomulur; parent'lar SQLite'ta durur ve chunk_id ile getirilir.
SCHEMA = pa.schema([
    pa.field("chunk_id", pa.string()),
    pa.field("parent_id", pa.string()),
    pa.field("doc_id", pa.string()),
    pa.field("kaynak_turu", pa.string()),
    pa.field("baglayicilik", pa.string()),
    pa.field("otorite_skoru", pa.int32()),
    pa.field("madde_no", pa.string()),
    pa.field("karar_no", pa.string()),
    pa.field("karar_tarihi", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 768)),
])


def connect():
    import lancedb
    settings.LANCE_DIR.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(settings.LANCE_DIR))


def _records(chunks: list[dict[str, Any]], vectors: np.ndarray) -> list[dict]:
    return [
        {
            "chunk_id": c["chunk_id"],
            "parent_id": c["parent_id"] or "",
            "doc_id": c["doc_id"],
            "kaynak_turu": c["kaynak_turu"],
            "baglayicilik": c["baglayicilik"],
            "otorite_skoru": int(c["otorite_skoru"]),
            "madde_no": c["madde_no"] or "",
            "karar_no": c["karar_no"] or "",
            "karar_tarihi": c["karar_tarihi"] or "",
            "vector": vectors[i].tolist(),
        }
        for i, c in enumerate(chunks)
    ]


def write(chunks: list[dict[str, Any]], vectors: np.ndarray, overwrite: bool = True):
    db = connect()
    rows = _records(chunks, vectors)
    if overwrite or TABLE not in db.table_names():
        return db.create_table(TABLE, data=rows, schema=SCHEMA, mode="overwrite")
    tbl = db.open_table(TABLE)
    tbl.delete(f"chunk_id IN ({','.join(repr(r['chunk_id']) for r in rows)})")
    tbl.add(rows)
    return tbl


def search(query_vec: np.ndarray, limit: int = 40, where: str | None = None) -> list[dict]:
    db = connect()
    if TABLE not in db.table_names():
        return []
    q = db.open_table(TABLE).search(query_vec).limit(limit)
    if where:
        q = q.where(where, prefilter=True)
    out = []
    for r in q.to_list():
        r.pop("vector", None)
        # LanceDB L2 uzakligi dondurur; vektorler normalize oldugu icin benzerlige cevrilir
        r["score"] = 1.0 - (r.get("_distance", 0.0) / 2.0)
        out.append(r)
    return out


def count() -> int:
    db = connect()
    return db.open_table(TABLE).count_rows() if TABLE in db.table_names() else 0
