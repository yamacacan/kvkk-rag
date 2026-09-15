# Hibrit retrieval: dense (LanceDB) + leksik (FTS5) -> RRF -> parent genisletme
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..config import settings
from ..index import embedder, lexical_store, vector_store
from . import rerank

RRF_K = 60
DENSE_TOPK = 40
LEXICAL_TOPK = 40
PARENT_LIMIT = 12
# Akademik kaynaklardaki "dayanaksiz cevap" riskine karsi: sonucta en az bu kadar
# zorunlu (kanun/yonetmelik/teblig/ilke/kurul karari) parca bulunmali.
# Zorunlu kaynaklar icin ayri gecisin derinligi. 10 secildi: R@10 (0.71) ve kayip
# (10/35) en iyi degerini burada aliyor ve hicbir soru dayanaksiz kalmiyor.
# MRR daha dusuk (0.380 vs 0.464) ama cevap tum kaynak kumesinden uretildigi icin
# operasyonel metrik ilk sira degil, ilk 10'da dogru dayanagin bulunmasidir.
MANDATORY_TOPK = 10
MIN_ZORUNLU = 3
# Otorite katsayisi: 0 = saf benzerlik, 1 = kanun maddesi temel skorunu iki katina cikarir.
# Cross-encoder logitlerinin min-max normalizasyonu sonrasi (HANDOFF.md / §5.5) w=2.0
# secildi: R@10 (0.77) ve kayip sayisi (8/35) w=2.0'de doyuma ulasiyor.
# w=3.0'daki minik MRR farki (0.657 -> 0.659) yalnizca yeniden siralama gurultusudur;
# w=5.0'de ise mevzuat lehine asiri zorlama nedeniyle R@1 ve MRR dusmektedir (0.645).
# En kucuk doyum noktasi w=2.0'dir.
AUTHORITY_WEIGHT = 2.0
# Cross-encoder'a gonderilecek aday sayisi. 80'de doyuyor (120 ayni sonucu veriyor,
# havuz tukeniyor). 40'ta kesmek R@10'u 0.77'den 0.69'a dusuruyordu: reranker dogruyu
# seciyor ama aday kumesine girmemis olani kurtaramaz.
RERANK_CANDIDATES = 80


@dataclass
class Hit:
    chunk_id: str
    parent_id: str | None
    score: float
    dense_rank: int | None = None
    lexical_rank: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _rrf(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / (RRF_K + rank)


def fuse(dense: list[dict], lexical: list[dict]) -> list[Hit]:
    ranks: dict[str, Hit] = {}
    for i, r in enumerate(dense, start=1):
        ranks[r["chunk_id"]] = Hit(r["chunk_id"], r.get("parent_id") or None, 0.0, dense_rank=i)
    for i, r in enumerate(lexical, start=1):
        h = ranks.get(r["chunk_id"])
        if h:
            h.lexical_rank = i
        else:
            ranks[r["chunk_id"]] = Hit(r["chunk_id"], r.get("parent_id") or None, 0.0, lexical_rank=i)

    for h in ranks.values():
        h.score = _rrf(h.dense_rank) + _rrf(h.lexical_rank)
    return sorted(ranks.values(), key=lambda h: h.score, reverse=True)


def search(query: str, conn=None, limit: int = PARENT_LIMIT,
           where: str | None = None, use_rerank: bool = True) -> list[dict]:
    own_conn = conn is None
    conn = conn or lexical_store.connect()
    try:
        qvec = embedder.embed_query(query)
        dense = vector_store.search(qvec, limit=DENSE_TOPK, where=where)
        lexical = lexical_store.search(conn, query, limit=LEXICAL_TOPK, level="child")

        # Karar ozetleri korpusun %87'si; filtresiz aramada baglayici mevzuat aday
        # havuzuna hic giremeyebiliyor. Zorunlu kaynaklar icin ayri bir gecis yapilir,
        # boylece kota yeniden siralama degil gercek bir garanti haline gelir.
        if where is None and MANDATORY_TOPK > 0:
            dense += vector_store.search(
                qvec, limit=MANDATORY_TOPK, where="baglayicilik LIKE 'zorunlu%'")
            lexical += lexical_store.search(
                conn, query, limit=MANDATORY_TOPK, level="child", baglayicilik="zorunlu")

        hits = fuse(dense, lexical)
        if not hits:
            return []

        child_meta = lexical_store.get_by_id(conn, [h.chunk_id for h in hits])

        # Parent bazinda tekillestir: ayni maddeden birden cok fikra gelirse en iyi skor
        parents: dict[str, dict] = {}
        for h in hits:
            meta = child_meta.get(h.chunk_id)
            if not meta:
                continue
            pid = meta["parent_id"] or h.chunk_id
            if pid not in parents or h.score > parents[pid]["score"]:
                parents[pid] = {"parent_id": pid, "score": h.score, "eslesen_child": meta}

        # Cross-encoder yeniden siralama: RRF siralamasi adaylari bulur ama hangisinin
        # soruyu gercekten cevapladigini ayirt edemiyor (bkz. deney raporu 6.7).
        cand = sorted(parents.values(), key=lambda p: p["score"], reverse=True)
        if use_rerank and len(cand) > 1:
            cand = cand[:RERANK_CANDIDATES]
            ce = rerank.score(query, [p["eslesen_child"]["text"] for p in cand])
            # Aday kumesi icinde min-max normalize; sabit sigmoid butun logitleri
            # ayni noktaya sikistirip otorite carpanini tek belirleyici yapiyordu.
            for p, raw, norm in zip(cand, ce, rerank.normalize(ce)):
                p["ce_score"] = float(raw)
                p["base_score"] = float(norm)
        else:
            for p in cand:
                p["ce_score"] = None
                p["base_score"] = p["score"]

        # Otorite agirlikli siralama: karar ozetleri korpusun %87'si oldugu icin
        # salt benzerlikte baglayici maddeyi listeden tamamen disari itiyorlar.
        for p in cand:
            otorite = p["eslesen_child"]["otorite_skoru"]
            p["final_score"] = p["base_score"] * (1.0 + AUTHORITY_WEIGHT * (otorite - 1) / 4.0)

        ordered = sorted(cand, key=lambda p: p["final_score"], reverse=True)
        selected = ordered[:limit]

        # Kota: yine de yeterli zorunlu kaynak yoksa yukari tasinir (sona eklenmez)
        n_zorunlu = sum(1 for p in selected
                        if p["eslesen_child"]["baglayicilik"].startswith("zorunlu"))
        if n_zorunlu < MIN_ZORUNLU:
            eksik = [p for p in ordered[limit:]
                     if p["eslesen_child"]["baglayicilik"].startswith("zorunlu")
                     ][:MIN_ZORUNLU - n_zorunlu]
            if eksik:
                selected = (selected[:limit - len(eksik)] + eksik)
                selected.sort(key=lambda p: p["final_score"], reverse=True)

        parent_rows = lexical_store.get_by_id(conn, [p["parent_id"] for p in selected])
        out = []
        for p in selected:
            row = parent_rows.get(p["parent_id"]) or p["eslesen_child"]
            out.append({**row, "score": p["final_score"], "rrf_score": p["score"],
                        "ce_score": p.get("ce_score"),
                        "eslesen_parca": p["eslesen_child"]["text_raw"][:300]})
        return out
    finally:
        if own_conn:
            conn.close()
