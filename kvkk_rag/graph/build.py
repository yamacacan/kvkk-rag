# Grafigi mevzuat korpusundan + envanterden insa eder.
from __future__ import annotations

import json
from typing import Any

from ..config import settings
from ..inventory import audit as inv_audit
from ..inventory import loader as inv_loader
from ..inventory import normalize, taxonomy
from . import schema as S


def _mevzuat_nodes(conn) -> dict[str, int]:
    # chunks tablosundaki parent'lar mevzuat ve karar dugumlerini verir
    rows = conn.execute("""
        SELECT DISTINCT kaynak_turu, belge_adi, madde_no, madde_basligi,
               karar_no, karar_tarihi, konu_ozeti, url, madde_atiflari
        FROM chunks WHERE level = 'parent'
    """).fetchall()

    nodes, edges = [], []
    mevzuat_seen: set[str] = set()

    for r in rows:
        tur = r["kaynak_turu"]
        if r["madde_no"]:
            mid = S.node_id(S.MEVZUAT, r["belge_adi"])
            if mid not in mevzuat_seen:
                mevzuat_seen.add(mid)
                nodes.append((mid, S.MEVZUAT, r["belge_adi"][:120],
                              {"kaynak_turu": tur, "url": r["url"]}))
            madde_key = f"{r['belge_adi'][:40]}|{r['madde_no']}"
            nid = S.node_id(S.MADDE, madde_key)
            nodes.append((nid, S.MADDE, f"{r['belge_adi'][:40]} m.{r['madde_no']}",
                          {"madde_no": r["madde_no"], "baslik": r["madde_basligi"],
                           "kaynak_turu": tur, "url": r["url"]}))
            edges.append((mid, nid, S.HAS_PART, 1.0, {}))
        elif r["karar_no"]:
            nid = S.node_id(S.KARAR, r["karar_no"])
            nodes.append((nid, S.KARAR, f"{tur} {r['karar_no']}",
                          {"kaynak_turu": tur, "tarih": r["karar_tarihi"],
                           "konu": (r["konu_ozeti"] or "")[:200], "url": r["url"]}))

    S.upsert_nodes(conn, nodes)
    S.upsert_edges(conn, edges)
    return {"mevzuat_dugum": len(nodes), "mevzuat_kenar": len(edges)}


def _citation_edges(conn) -> int:
    # Kararlarin metninden cikarilan madde atiflari -> CITES
    rows = conn.execute("""
        SELECT karar_no, madde_atiflari FROM chunks
        WHERE level = 'parent' AND karar_no IS NOT NULL AND madde_atiflari != '[]'
    """).fetchall()

    kanun_maddeleri = {
        r["id"]: r["id"] for r in conn.execute(
            "SELECT id FROM nodes WHERE type = ? AND json_extract(props,'$.kaynak_turu') = 'kanun'",
            (S.MADDE,)).fetchall()
    }
    by_no: dict[str, str] = {}
    for nid in kanun_maddeleri:
        no = nid.rsplit("|", 1)[-1]
        by_no[no] = nid

    edges = []
    for r in rows:
        src = S.node_id(S.KARAR, r["karar_no"])
        for ref in json.loads(r["madde_atiflari"]):
            parts = ref.split("/")
            if len(parts) < 2 or parts[0] != "6698":
                continue
            madde_no = parts[1]
            dst = by_no.get(madde_no)
            if dst:
                edges.append((src, dst, S.CITES, 1.0, {"ref": ref}))
    return S.upsert_edges(conn, edges)


def _taxonomy_nodes(conn) -> int:
    nodes, edges = [], []
    kanun_madde = {
        nid.rsplit("|", 1)[-1]: nid for (nid,) in conn.execute(
            "SELECT id FROM nodes WHERE type = ? AND json_extract(props,'$.kaynak_turu')='kanun'",
            (S.MADDE,)).fetchall()
    }

    for it in taxonomy.load().get("hukuki_sebep", []):
        nid = S.node_id(S.HUKUKI_SEBEP, it["ad"])
        nodes.append((nid, S.HUKUKI_SEBEP, it["ad"], {"grup": it["aciklama"]}))
        madde = taxonomy.SEBEP_GRUBU_MADDE.get(it["aciklama"])
        if madde and madde in kanun_madde:
            edges.append((nid, kanun_madde[madde], S.TANIMLI_MADDE, 1.0,
                          {"kaynak": "seeder grubu"}))

    for kind, ntype in (("isleme_amaci", S.ISLEME_AMACI), ("alici_grubu", S.ALICI_GRUBU),
                        ("teknik_tedbir", S.TEKNIK_TEDBIR), ("idari_tedbir", S.IDARI_TEDBIR)):
        for ad in taxonomy.values(kind):
            nodes.append((S.node_id(ntype, ad), ntype, ad, {}))

    for kat in taxonomy.OZEL_NITELIKLI_KATEGORILER:
        nid = S.node_id(S.VERI_KATEGORISI, kat)
        nodes.append((nid, S.VERI_KATEGORISI, kat, {"ozel_nitelikli": True}))
        if "6" in kanun_madde:
            edges.append((nid, kanun_madde["6"], S.OZEL_NITELIKLI, 1.0, {}))

    S.upsert_nodes(conn, nodes)
    S.upsert_edges(conn, edges)
    return len(nodes)


def _inventory_nodes(conn, rows: list[inv_loader.InventoryRow]) -> dict[str, int]:
    nodes, edges = [], []
    sebep_canon = taxonomy.values("hukuki_sebep")

    for row in rows:
        rid = S.node_id(S.ENVANTER, str(row.satir_no))
        nodes.append((rid, S.ENVANTER, f"Satır {row.satir_no}",
                      {"faaliyet": row.faaliyet, "birim": row.birim,
                       "veri_kategorisi": row.veri_kategorisi,
                       "bulgu_sayisi": len(row.bulgular)}))

        if row.birim:
            bid = S.node_id(S.BIRIM, row.birim)
            nodes.append((bid, S.BIRIM, row.birim, {}))
            edges.append((rid, bid, S.AIT_BIRIM, 1.0, {}))
        if row.faaliyet:
            fid = S.node_id(S.FAALIYET, row.faaliyet)
            nodes.append((fid, S.FAALIYET, row.faaliyet, {}))
            edges.append((rid, fid, S.AIT_FAALIYET, 1.0, {}))
        if row.veri_kategorisi:
            kid = S.node_id(S.VERI_KATEGORISI, row.veri_kategorisi)
            nodes.append((kid, S.VERI_KATEGORISI, row.veri_kategorisi,
                          {"ozel_nitelikli": taxonomy.is_ozel_nitelikli_kategori(row.veri_kategorisi)}))
            edges.append((rid, kid, S.ICERIR, 1.0, {}))
        if row.hukuki_sebep:
            m = normalize.match_one(row.hukuki_sebep, sebep_canon)
            if m.kanonik:
                sid = S.node_id(S.HUKUKI_SEBEP, m.kanonik)
                edges.append((rid, sid, S.DAYANAK, m.guven,
                              {"ham": row.hukuki_sebep[:120], "yontem": m.yontem}))
        for alan, kind, ntype, etype in (
            ("isleme_amaci", "isleme_amaci", S.ISLEME_AMACI, S.AMAC),
            ("alici_grubu", "alici_grubu", S.ALICI_GRUBU, S.AKTARIR),
            ("teknik_tedbir", "teknik_tedbir", S.TEKNIK_TEDBIR, S.TEDBIR),
            ("idari_tedbir", "idari_tedbir", S.IDARI_TEDBIR, S.TEDBIR),
        ):
            raw = getattr(row, alan)
            if not raw:
                continue
            for m in normalize.match_multi(raw, kind):
                if m.kanonik and m.yontem != normalize.CUSTOM:
                    edges.append((rid, S.node_id(ntype, m.kanonik), etype,
                                  m.guven, {"yontem": m.yontem}))

        for b in row.bulgular:
            bid = S.node_id(S.BULGU, f"{row.satir_no}-{b['kod']}-{b.get('alan') or ''}")
            nodes.append((bid, S.BULGU, b["baslik"],
                          {"kod": b["kod"], "seviye": b["seviye"],
                           "dayanak": b["dayanak"], "aciklama": b["aciklama"][:300]}))
            edges.append((bid, rid, S.BULGU_OF, 1.0, {}))

    S.upsert_nodes(conn, nodes)
    S.upsert_edges(conn, edges)
    return {"envanter_dugum": len(nodes), "envanter_kenar": len(edges)}


def build(rebuild: bool = True) -> dict[str, Any]:
    conn = S.connect()
    try:
        if rebuild:
            S.clear(conn)

        out: dict[str, Any] = {}
        out.update(_mevzuat_nodes(conn))
        out["taksonomi_dugum"] = _taxonomy_nodes(conn)
        out["cites_kenar"] = _citation_edges(conn)

        rows, _ = inv_loader.load()
        inv_audit.audit(rows)
        out.update(_inventory_nodes(conn, rows))

        conn.commit()
        out["stats"] = S.stats(conn)
        return out
    finally:
        conn.close()
