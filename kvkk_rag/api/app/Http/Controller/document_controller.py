"""Uyum belgeleri ve kurum profili. Belgeler kapsam filtreli envanterden uretilir:
documents.view / documents.generate kapsami hangi satirlarin belgeye girecegini belirler.

Uretim senkron degildir: POST /generate ve /generate-all bir `generated_documents`
kaydi acip GenerateDocumentJob'u kuyruga yazar (202). Worker belgeyi uretince
DocumentGenerated olayi kullaniciya bildirim dusurur; dosya GET /uretilen/{id}/indir
ile alinir. Kayitlar kullaniciya ozeldir (kendi belgeleri)."""
from __future__ import annotations

import sqlite3
from typing import Any
from urllib.parse import quote

from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

from .....compliance import generate as comp_generate
from .....compliance import store as comp_store
from ....database.connection import get_db
from ...Events import DocumentRequested, KurumProfiliGuncellendi, dispatch
from ...Jobs.generate_document_job import GenerateDocumentJob
from ...Models.audit_log import AuditLog
from ...Models.generated_document import GeneratedDocument
from ...Models.user import User
from ...Services.document_service import DocumentService
from ...Services.inventory_service import InventoryService
from ..Middleware.authenticate import authenticate
from ..Request.document import DocumentRequest, ProfileRequest
from .base import Controller, route

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MODULE = "documents"


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    return ileri.split(",")[0].strip() if ileri else (request.client.host if request.client else None)


class ProfileController(Controller):
    prefix = "/api/profile"
    tags = ["profil"]
    middleware = (authenticate,)

    @route("GET", "", permission="profile.view")
    def show(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return comp_store.get(conn)

    @route("PUT", "", permission="profile.update")
    def update(self, payload: ProfileRequest, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if not payload.kurum.strip():
            raise HTTPException(400, "Kurum adı zorunludur")
        once = comp_store.get(conn)
        sonuc = comp_store.save(conn, payload.model_dump())
        AuditLog.record(conn, "profile.update", actor=user, target_type="KurumProfili", target_label=payload.kurum,
                        before={k: v for k, v in once.items() if k != "guncelleme"},
                        after={k: v for k, v in sonuc.items() if k != "guncelleme"},
                        ip=request.client.host if request.client else None)
        if any(once.get(k) != sonuc.get(k) for k in ("kurum", "adres", "web_adres", "cagri_merkezi")):
            # faaliyet belgeleri kurum bilgisini tasir: hepsi kuyrukta yenilenir
            dispatch(KurumProfiliGuncellendi(user=user, conn=conn, once=once, sonra=sonuc))
        return sonuc


class DocumentController(Controller):
    prefix = "/api/documents"
    tags = ["belgeler"]
    middleware = (authenticate,)

    @route("GET", "", permission="documents.view")
    def index(self) -> dict[str, Any]:
        return DocumentService.templates()

    @route("GET", "/faaliyetler", permission="documents.view")
    def faaliyetler(self, birim: str | None = None, user: User = Depends(authenticate),
                    conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Aydinlatma metni faaliyet bazlidir; her faaliyetin kendi metni olur.
        rows = DocumentService.narrow(InventoryService.rows(conn, user, MODULE, "view"), birim)
        return {"faaliyetler": DocumentService.faaliyetler(rows)}

    @route("POST", "/preview", permission="documents.view")
    def preview(self, req: DocumentRequest, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Belgeyi uretmeden once hangi alanlarin bos kalacagini gosterir
        rows = DocumentService.narrow(InventoryService.rows(conn, user, MODULE, "view"),
                                      req.birim, req.faaliyet_filtresi)
        out = DocumentService.preview(req, rows)
        if out is None:
            raise HTTPException(404, f"Şablon bulunamadı: {req.sablon}")
        return out

    # ---- uretim: kuyruga alinir, worker uretir, bildirim gelir ----
    def _kuyruga_al(self, req: DocumentRequest, tur: str, request: Request, user: User,
                    conn: sqlite3.Connection) -> dict[str, Any]:
        if not req.kurum.strip():
            raise HTTPException(400, "Kurum adı zorunludur")
        if req.sablon not in comp_generate.SABLONLAR:
            raise HTTPException(404, f"Bilinmeyen şablon: {req.sablon}")
        belge = GeneratedDocument.open(conn, user.id, req.sablon, comp_generate.BELGE_ADI.get(req.sablon, req.sablon),
                                       tur, req.model_dump())
        job = GenerateDocumentJob(belge.id).dispatch(conn=conn, user_id=user.id)
        belge.update(conn, job_id=job.id)
        dispatch(DocumentRequested(document=belge, user=user, conn=conn, ip=_ip(request)))
        return {"belge": belge.to_dict(), "job_id": job.id, "kuyrukta": True}

    @route("POST", "/generate", permission="documents.generate", status_code=202)
    def generate(self, req: DocumentRequest, request: Request, user: User = Depends(authenticate),
                 conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return self._kuyruga_al(req, "docx", request, user, conn)

    @route("POST", "/generate-all", permission="documents.generate", status_code=202)
    def generate_all(self, req: DocumentRequest, request: Request, user: User = Depends(authenticate),
                     conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return self._kuyruga_al(req, "zip", request, user, conn)

    # ---- uretilen belgeler (kullanicinin kendi kayitlari) ----
    @route("GET", "/uretilen", permission="documents.view")
    def uretilenler(self, limit: int = 30, user: User = Depends(authenticate),
                    conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        belgeler = GeneratedDocument.for_user(conn, user.id, limit=min(limit, 100))
        return {"belgeler": [b.to_dict() for b in belgeler],
                "bekleyen": GeneratedDocument.pending_count(conn, user.id)}

    def _belgem(self, conn: sqlite3.Connection, user: User, belge_id: int) -> GeneratedDocument:
        belge = self.find_or_fail(GeneratedDocument.find(conn, belge_id), "Belge bulunamadı")
        if belge.user_id != user.id and not user.is_super(conn):
            raise HTTPException(403, "Bu belge size ait değil.")
        return belge

    @route("GET", "/uretilen/{belge_id}", permission="documents.view")
    def uretilen(self, belge_id: int, user: User = Depends(authenticate),
                 conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"belge": self._belgem(conn, user, belge_id).to_dict()}

    @route("GET", "/uretilen/{belge_id}/indir", permission="documents.generate")
    def indir(self, belge_id: int, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> Response:
        belge = self._belgem(conn, user, belge_id)
        if not belge.ready:
            raise HTTPException(409, "Belge henüz hazır değil." if belge.durum != "hata" else f"Belge üretilemedi: {belge.hata}")
        basliklar = {"Content-Disposition": f'attachment; filename="{quote(belge.ad)}"'}
        if belge.kalan:
            basliklar["X-Doldurulmayan-Alanlar"] = ",".join(belge.to_dict()["kalan"])
        ai = belge.to_dict()["yapay_zeka"]
        if ai:
            basliklar["X-Yapay-Zeka-Bolumleri"] = ",".join(ai)
        return FileResponse(str(belge.path), media_type=belge.mime, headers=basliklar, filename=belge.ad)

    @route("DELETE", "/uretilen/{belge_id}", permission="documents.view")
    def uretilen_sil(self, belge_id: int, user: User = Depends(authenticate),
                     conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        belge = self._belgem(conn, user, belge_id)
        if belge.durum in ("kuyrukta", "uretiliyor"):
            raise HTTPException(409, "Üretimi süren belge silinemez; bitmesini bekleyin.")
        belge.delete(conn)
        return {"silindi": belge_id}
