from __future__ import annotations

from typing import Any

from .....config import settings
from .base import Controller, route


class HealthController(Controller):
    tags = ["sistem"]

    @route("GET", "/api/health")
    def health(self) -> dict[str, Any]:
        # Retrieval modulu agir (torch); yalnizca sabitini okumak icin tembel import
        try:
            from .....retrieval import hybrid
            agirlik = hybrid.AUTHORITY_WEIGHT
        except Exception:  # noqa: BLE001
            agirlik = None
        return {
            "status": "ok",
            "rerank_model": settings.RERANK_MODEL,
            "embed_model": settings.EMBED_MODEL,
            "default_llm": settings.LLM_PROVIDER,
            "authority_weight": agirlik,
            "auth": "bearer",
        }
