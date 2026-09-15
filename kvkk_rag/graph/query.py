# Graf sorgulari. SQLite uzerinde; networkx yalnizca yol bulma icin turetilir.
from __future__ import annotations

import json
from typing import Any

from . import schema as S


def _row(r) -> dict[str, Any]:
    d = dict(r)
    if "props" in d and isinstance(d["props"], str):
        d["props"] = json.loads(d["props"])
    return d


def node(conn, node_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return _row(r) if r else None


def nodes_by_type(conn, ntype: str, limit: int = 100, offset: int = 0) -> list[dict]:
    rs = conn.execute("SELECT * FROM nodes WHERE type = ? ORDER BY label LIMIT ? OFFSET ?",
                      (ntype, limit, offset)).fetchall()
    return [_row(r) for r in rs]


def neighbors(conn, node_id: str, edge_type: str | None = None,
              direction: str = "both", limit: int = 50) -> list[dict]:
    out = []
    if direction in ("out", "both"):
        sql = "SELECT e.type AS kenar, e.weight, n.* FROM edges e JOIN nodes n ON n.id = e.dst WHERE e.src = ?"
        params: list[Any] = [node_id]
        if edge_type:
            sql += " AND e.type = ?"
            params.append(edge_type)
        out += [{**_row(r), "yon": "out"} for r in conn.execute(sql + " LIMIT ?", params + [limit])]
    if direction in ("in", "both"):
        sql = "SELECT e.type AS kenar, e.weight, n.* FROM edges e JOIN nodes n ON n.id = e.src WHERE e.dst = ?"
        params = [node_id]
        if edge_type:
            sql += " AND e.type = ?"
            params.append(edge_type)
        out += [{**_row(r), "yon": "in"} for r in conn.execute(sql + " LIMIT ?", params + [limit])]
    return out


def ozel_nitelikli_ihlaller(conn, limit: int = 100) -> list[dict]:
    # "Hangi faaliyetlerim ozel nitelikli veri isliyor ve dayanagi gecersiz?"
    sql = """
        SELECT b.label AS bulgu, b.props AS bulgu_props,
               e.props AS envanter_props, e.id AS envanter_id
        FROM nodes b
        JOIN edges eo ON eo.src = b.id AND eo.type = ?
        JOIN nodes e  ON e.id = eo.dst
        WHERE b.type = ? AND json_extract(b.props,'$.kod') = 'ENV-004'
        LIMIT ?
    """
    rs = conn.execute(sql, (S.BULGU_OF, S.BULGU, limit)).fetchall()
    out = []
    for r in rs:
        bp = json.loads(r["bulgu_props"])
        ep = json.loads(r["envanter_props"])
        out.append({
            "envanter_id": r["envanter_id"], "bulgu": r["bulgu"],
            "seviye": bp.get("seviye"), "dayanak": bp.get("dayanak"),
            "faaliyet": ep.get("faaliyet"), "birim": ep.get("birim"),
            "veri_kategorisi": ep.get("veri_kategorisi"),
        })
    return out


def faaliyet_riski(conn, limit: int = 20) -> list[dict]:
    # Bulgu sayisina gore en riskli faaliyetler
    sql = """
        SELECT f.label AS faaliyet, COUNT(DISTINCT b.id) AS bulgu,
               SUM(CASE WHEN json_extract(b.props,'$.seviye')='kritik' THEN 1 ELSE 0 END) AS kritik,
               COUNT(DISTINCT e.id) AS satir
        FROM nodes f
        JOIN edges ef ON ef.dst = f.id AND ef.type = ?
        JOIN nodes e  ON e.id = ef.src
        LEFT JOIN edges eb ON eb.dst = e.id AND eb.type = ?
        LEFT JOIN nodes b  ON b.id = eb.src
        WHERE f.type = ?
        GROUP BY f.id ORDER BY kritik DESC, bulgu DESC LIMIT ?
    """
    rs = conn.execute(sql, (S.AIT_FAALIYET, S.BULGU_OF, S.FAALIYET, limit)).fetchall()
    return [dict(r) for r in rs]


def madde_etkisi(conn, madde_no: str) -> dict[str, Any]:
    # Bir KVKK maddesine bagli her sey: atif yapan kararlar, dayanan sebepler
    sql_madde = """
        SELECT id, label, props FROM nodes
        WHERE type = ? AND json_extract(props,'$.kaynak_turu')='kanun'
          AND json_extract(props,'$.madde_no') = ?
    """
    m = conn.execute(sql_madde, (S.MADDE, madde_no)).fetchone()
    if not m:
        return {}
    kararlar = neighbors(conn, m["id"], S.CITES, "in", limit=200)
    sebepler = neighbors(conn, m["id"], S.TANIMLI_MADDE, "in", limit=50)
    return {
        "madde": _row(m),
        "atif_yapan_karar": len(kararlar),
        "kararlar": kararlar[:20],
        "hukuki_sebepler": [s["label"] for s in sebepler],
    }
