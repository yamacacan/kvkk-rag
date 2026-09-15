# Retrieval degerlendirme. Altin kaynak eslesmesi ve recall/MRR/nDCG.
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ..config import settings


def load_gold() -> list[dict]:
    path = settings.DATA_DIR / "eval" / "gold_set.json"
    return json.loads(path.read_text(encoding="utf-8"))["sorular"]


def matches(row: dict[str, Any], gold: dict[str, Any]) -> bool:
    # Altin kayitta belirtilen TUM alanlar tutmali; belirtilmeyenler serbest
    if "kaynak_turu" in gold and row.get("kaynak_turu") != gold["kaynak_turu"]:
        return False
    if "madde_no" in gold and str(row.get("madde_no") or "") != gold["madde_no"]:
        return False
    if "karar_no" in gold and str(row.get("karar_no") or "") != gold["karar_no"]:
        return False
    if "belge_iceren" in gold and gold["belge_iceren"].lower() not in str(row.get("belge_adi") or "").lower():
        return False
    return True


def first_hit_rank(rows: list[dict], golds: list[dict]) -> int | None:
    for i, row in enumerate(rows, start=1):
        if any(matches(row, g) for g in golds):
            return i
    return None


def evaluate(results: dict[str, list[dict]], gold: list[dict]) -> dict[str, Any]:
    # results: soru_id -> siralanmis parent satirlari
    ranks: list[int | None] = []
    per_q = []
    for q in gold:
        rows = results.get(q["id"], [])
        r = first_hit_rank(rows, q["altin"])
        ranks.append(r)
        per_q.append({"id": q["id"], "tip": q["tip"], "zorluk": q["zorluk"], "rank": r})

    n = len(ranks)
    def recall_at(k: int) -> float:
        return sum(1 for r in ranks if r is not None and r <= k) / n

    mrr = sum(1.0 / r for r in ranks if r is not None) / n
    ndcg = sum(1.0 / math.log2(r + 1) for r in ranks if r is not None) / n

    by_tip: dict[str, list] = {}
    for p in per_q:
        by_tip.setdefault(p["tip"], []).append(p["rank"])

    return {
        "n": n,
        "recall@1": recall_at(1),
        "recall@3": recall_at(3),
        "recall@5": recall_at(5),
        "recall@10": recall_at(10),
        "mrr": mrr,
        "ndcg": ndcg,
        "bulunamayan": sum(1 for r in ranks if r is None),
        "tip_bazli_recall@5": {
            t: sum(1 for r in rs if r is not None and r <= 5) / len(rs)
            for t, rs in by_tip.items()
        },
        "per_question": per_q,
    }
