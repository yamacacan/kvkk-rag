"""Uyum belgesi uretimi (docx / tum faaliyetler zip) — kuyrukta calisir.

Istek aninda `generated_documents` kaydi 'kuyrukta' acilir ve bu is kuyruga
yazilir. Worker calistirdiginda: kullanicinin documents.generate KAPSAMI ile
envanter okunur (kapsam istek aninda degil, uretim aninda cozulur), belge
uretilir, dosya diske yazilir, kayit 'hazir' olur ve DocumentGenerated olayi
dinleyicilere gider (bildirim + denetim gunlugu). Hata: kayit 'hata',
DocumentFailed olayi. Idempotent: kayit zaten 'hazir' ise yeniden uretmez."""
from __future__ import annotations

import json
import logging
import time

from ...database.connection import connect
from ..Events import DocumentFailed, DocumentGenerated, dispatch
from ..Models.generated_document import HATA, HAZIR, URETILIYOR, GeneratedDocument
from ..Models.user import User
from .base import Job, ShouldQueue

logger = logging.getLogger("kvkk_rag.api.jobs")


class GenerateDocumentJob(Job, ShouldQueue):
    queue = "documents"
    max_attempts = 1

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id

    def handle(self) -> None:
        from ..Http.Request.document import DocumentRequest
        from ..Services.document_service import DocumentService
        from ..Services.inventory_service import InventoryService

        conn = connect()
        try:
            belge = GeneratedDocument.find(conn, self.document_id)
            if belge is None:
                logger.warning("Belge kaydi yok: %s", self.document_id)
                return
            if belge.durum == HAZIR and belge.ready:
                return  # ayni is iki kez calisti; dosya zaten var
            user = User.find(conn, belge.user_id)
            if user is None or not user.active:
                belge.fail(conn, "Kullanıcı bulunamadı veya pasif")
                dispatch(DocumentFailed(document=belge, error="Kullanıcı bulunamadı veya pasif", conn=conn))
                return
            belge.update(conn, durum=URETILIYOR)
            t0 = time.perf_counter()
            try:
                req = DocumentRequest(**belge.request_data)
                rows = DocumentService.narrow(InventoryService.rows(conn, user, "documents", "generate"),
                                              req.birim, None if belge.tur == "zip" else req.faaliyet_filtresi)
                if belge.tur == "zip":
                    icerik, ad, uretilen, hatalar = DocumentService.generate_all(req, rows)
                    belge.store_file(conn, icerik, ad, uretilen=uretilen, satir=len(rows),
                                     hatalar=json.dumps(hatalar, ensure_ascii=False))
                else:
                    icerik, kalan, ad, kaynak = DocumentService.generate(req, rows)
                    ai = sorted(k for k, v in kaynak.items() if v == "yapay_zeka")
                    belge.store_file(conn, icerik, ad, satir=len(rows), uretilen=1,
                                     kalan=json.dumps(kalan, ensure_ascii=False),
                                     yapay_zeka=json.dumps(ai, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001 - hata kayda islenir, olay atilir, worker'a da yukselir
                belge.fail(conn, f"{type(e).__name__}: {e}")
                dispatch(DocumentFailed(document=belge, error=str(e), conn=conn))
                raise
            sure = round((time.perf_counter() - t0) * 1000)
            logger.info("Belge uretildi #%s %s (%s ms)", belge.id, belge.ad, sure)
            dispatch(DocumentGenerated(document=belge, conn=conn, duration_ms=sure))
        finally:
            conn.close()

    def failed(self, error: Exception) -> None:
        # Deneme hakki bitti; kayit handle() icinde zaten 'hata' yapildi. Kayit
        # 'uretiliyor'da kaldiysa (beklenmedik cokme) burada kapatilir.
        conn = connect()
        try:
            belge = GeneratedDocument.find(conn, self.document_id)
            if belge is not None and belge.durum not in (HAZIR, HATA):
                belge.fail(conn, f"{type(error).__name__}: {error}")
                dispatch(DocumentFailed(document=belge, error=str(error), conn=conn))
        finally:
            conn.close()
