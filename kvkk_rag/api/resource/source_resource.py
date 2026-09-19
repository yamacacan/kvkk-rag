from __future__ import annotations

from typing import Any

from .base import Resource


class SourceResource(Resource):
    # item: hibrit aramadan donen kaynak sozlugu
    def to_array(self) -> dict[str, Any]:
        r = self.item
        ce = r.get("ce_score")
        return {
            "baglayicilik": r.get("baglayicilik"),
            "kaynak_turu": r.get("kaynak_turu"),
            "madde_no": r.get("madde_no"),
            "karar_no": r.get("karar_no"),
            "belge_adi": r.get("belge_adi"),
            "score": round(float(r.get("score", 0)), 4),
            "ce_score": round(float(ce), 4) if ce is not None else None,
            "eslesen_parca": r.get("eslesen_parca", ""),
            "text": (r.get("text") or "")[:1200],
        }
