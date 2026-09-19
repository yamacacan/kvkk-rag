from __future__ import annotations

from typing import Any

from .base import Resource

# Bulgu seviyesi -> risk agirligi (arayuz ve GraphQL ile ayni)
AGIRLIK = {"kritik": 10, "yuksek": 5, "orta": 2, "dusuk": 1}


def risk_skoru(bulgular: list[dict[str, Any]]) -> int:
    return sum(AGIRLIK.get(b.get("seviye", ""), 0) for b in bulgular)


class EnvanterResource(Resource):
    # item: kvkk_rag.inventory.loader.InventoryRow (bulgular doldurulmus)
    def to_array(self) -> dict[str, Any]:
        r = self.item
        d = r.to_dict()
        d["risk_skoru"] = risk_skoru(r.bulgular)
        return d


class FindingResource(Resource):
    # item: kvkk_rag.inventory.audit.Finding
    def to_array(self) -> dict[str, Any]:
        return self.item.to_dict()
