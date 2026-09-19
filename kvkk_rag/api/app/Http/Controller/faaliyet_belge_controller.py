"""Faaliyet belgeleri: envanterdeki her faaliyet icin otomatik uretilip guncel tutulan
Aydinlatma Metni ve Acik Riza Beyani. Liste kullanicinin documents.view kapsamindaki
faaliyetlerle sinirlidir; eksik belgeler ilk listelemede kuyruga alinir."""
from __future__ import annotations

import sqlite3
from typing import Any
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from ....database.connection import get_db
from ...Jobs.faaliyet_belgesi_job import FaaliyetBelgeleriTopluJob
from ...Models.audit_log import AuditLog
from ...Models.faaliyet_belgesi import FaaliyetBelgesi
from ...Models.generated_document import MIME
from ...Models.user import User
from ...Services.faaliyet_belge_service import FaaliyetBelgeService
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class FaaliyetBelgeController(Controller):
    prefix = "/api/faaliyet-belgeleri"
    tags = ["faaliyet-belgeleri"]
    middleware = (authenticate,)

    @route("GET", "", permission="documents.view")
    def index(self, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return FaaliyetBelgeService.liste(conn, user)

    @route("POST", "/yenile", permission="documents.generate")
    def yenile(self, request: Request, faaliyet: str | None = None, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # faaliyet verilirse yalnizca o; yoksa kullanicinin gorebildigi tum faaliyetler (super: hepsi, toplu is)
        gorunur = FaaliyetBelgeService.kullanici_faaliyetleri(conn, user)
        if faaliyet:
            if faaliyet not in gorunur:
                raise HTTPException(403, "Bu faaliyet yetki kapsamınızın dışında.")
            n = FaaliyetBelgeService.yenile(conn, faaliyet, user_id=user.id)
            hedef = faaliyet
        elif user.is_super(conn):
            FaaliyetBelgeleriTopluJob(user.id).dispatch(conn=conn, user_id=user.id)
            n, hedef = len(gorunur), "tüm faaliyetler"
        else:
            n = sum(FaaliyetBelgeService.yenile(conn, f, user_id=user.id) for f in gorunur)
            hedef = f"{len(gorunur)} faaliyet"
        AuditLog.record(conn, "documents.refresh", actor=user, target_type="FaaliyetBelgesi", target_label=hedef,
                        after={"kuyruga_alinan": n}, ip=request.client.host if request.client else None)
        return {"kuyruga_alinan": n, "hedef": hedef}

    def _belgem(self, conn: sqlite3.Connection, user: User, belge_id: int) -> FaaliyetBelgesi:
        b = self.find_or_fail(FaaliyetBelgesi.find(conn, belge_id), "Belge bulunamadı")
        if b.faaliyet not in FaaliyetBelgeService.kullanici_faaliyetleri(conn, user):
            raise HTTPException(403, "Bu faaliyet yetki kapsamınızın dışında.")
        return b

    @route("GET", "/{belge_id}", permission="documents.view")
    def show(self, belge_id: int, user: User = Depends(authenticate),
             conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"belge": self._belgem(conn, user, belge_id).to_dict()}

    @route("GET", "/{belge_id}/indir", permission="documents.view")
    def indir(self, belge_id: int, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> Response:
        b = self._belgem(conn, user, belge_id)
        if not b.ready:
            raise HTTPException(409, "Belge henüz üretilmedi." if b.durum != "hata" else f"Belge üretilemedi: {b.hata}")
        ad = b.ad or f"{b.sablon}.docx"
        return FileResponse(str(b.path), media_type=MIME["docx"], filename=ad,
                            headers={"Content-Disposition": f'attachment; filename="{quote(ad)}"',
                                     "X-Belge-Durumu": b.durum})
