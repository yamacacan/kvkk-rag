"""Denetim gunlugu (audit trail): listeleme ve arayuzden sayfa goruntuleme bildirimi.
Sayfa goruntulemeleri (page.view) de gunluge yazilir; listede `sayfa_goruntuleme=false`
ile gizlenebilir."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, Request
from pydantic import BaseModel, Field

from ....database.connection import get_db
from ...Events import PageViewed, dispatch
from ...Models.audit_log import AuditLog
from ...Models.user import User
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class PageViewRequest(BaseModel):
    path: str = Field(min_length=1, max_length=300)
    name: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=120)


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    return ileri.split(",")[0].strip() if ileri else (request.client.host if request.client else None)


class AuditLogController(Controller):
    prefix = "/api/audit-logs"
    tags = ["yonetim"]
    middleware = (authenticate,)

    @route("GET", "", permission="audit.view")
    def index(self, action: str | None = None, user_id: int | None = None, arama: str | None = None,
              sayfa_goruntuleme: bool = True, limit: int = 50, offset: int = 0,
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        q = AuditLog.query(conn)
        if action:
            q.where("action", "LIKE", action.rstrip("*") + "%")
        elif not sayfa_goruntuleme:
            q.where("action", "!=", "page.view")
        if user_id:
            q.where("user_id", user_id)
        if arama:
            q.where_group(lambda g: g.where("user_email", "LIKE", f"%{arama}%")
                          .or_where("target_label", "LIKE", f"%{arama}%")
                          .or_where("action", "LIKE", f"%{arama}%"))
        toplam = q.count()
        kayitlar = q.order_by("id", "DESC").limit(min(limit, 500)).offset(offset).get()
        eylemler = [r[0] for r in conn.execute("SELECT DISTINCT action FROM audit_logs ORDER BY action")]
        return {"toplam": toplam, "offset": offset, "limit": limit,
                "kayitlar": [k.to_dict() for k in kayitlar], "eylemler": eylemler}

    @route("POST", "/page-view")
    def page_view(self, req: PageViewRequest, request: Request, user: User = Depends(authenticate),
                  conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Her oturum acmis kullanici kendi sayfa goruntulemesini bildirir (izin gerekmez)
        dispatch(PageViewed(user=user, conn=conn, path=req.path, name=req.name, title=req.title, ip=_ip(request)))
        return {"kaydedildi": True}
