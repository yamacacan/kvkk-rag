"""Belge istegi / uretimi / hatasi -> denetim gunlugu (documents.*)."""
from __future__ import annotations

from ..Events import DocumentFailed, DocumentGenerated, DocumentRequested
from ..Models.audit_log import AuditLog
from ..Models.user import User


class LogDocumentActivity:
    def handle(self, event: DocumentRequested | DocumentGenerated | DocumentFailed) -> None:
        b = event.document
        etiket = f"{b.get('sablon_adi') or b.sablon} (#{b.id})"
        if isinstance(event, DocumentRequested):
            istek = b.request_data or {}
            AuditLog.record(event.conn, "documents.generate", actor=event.user, target_type="Belge",
                            target_id=b.id, target_label=etiket,
                            after={"sablon": b.sablon, "tur": b.get("tur"), "job_id": b.get("job_id"),
                                   "birim": istek.get("birim"), "faaliyet": istek.get("faaliyet_filtresi")},
                            ip=event.ip)
            return
        # Worker'da calisir: aktor, belgeyi isteyen kullanicidir
        actor = User.find(event.conn, b.user_id)
        if isinstance(event, DocumentGenerated):
            AuditLog.record(event.conn, "documents.ready", actor=actor, target_type="Belge", target_id=b.id,
                            target_label=etiket,
                            after={"ad": b.get("ad"), "boyut": b.get("boyut"), "satir": b.get("satir"),
                                   "sure_ms": event.duration_ms})
        else:
            AuditLog.record(event.conn, "documents.failed", actor=actor, target_type="Belge", target_id=b.id,
                            target_label=etiket, after={"hata": event.error})
