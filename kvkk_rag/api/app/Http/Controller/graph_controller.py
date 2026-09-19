from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from .....graph import query as GQ
from .....graph import schema as GS
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class GraphController(Controller):
    prefix = "/api/graph"
    tags = ["graf"]
    middleware = (authenticate,)

    @route("GET", "/risk", permission="graph.view")
    def risk(self, limit: int = 10) -> dict[str, Any]:
        conn = GS.connect()
        try:
            return {"faaliyetler": GQ.faaliyet_riski(conn, limit), "graf": GS.stats(conn)}
        finally:
            conn.close()

    @route("GET", "/madde/{madde_no}", permission="graph.view")
    def madde(self, madde_no: str) -> dict[str, Any]:
        conn = GS.connect()
        try:
            out = GQ.madde_etkisi(conn, madde_no)
            if not out:
                raise HTTPException(404, f"KVKK m.{madde_no} grafta bulunamadı")
            return out
        finally:
            conn.close()
