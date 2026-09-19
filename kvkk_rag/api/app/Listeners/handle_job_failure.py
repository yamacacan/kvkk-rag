"""Kuyruktaki is kalici olarak basarisiz oldu -> denetim gunlugu + (belge isi
degilse; onun kendi bildirimi var) isi baslatan kullaniciya bildirim."""
from __future__ import annotations

from ..Events import JobFailed
from ..Models.audit_log import AuditLog
from ..Models.notification import Notification
from ..Models.user import User


class HandleJobFailure:
    def handle(self, event: JobFailed) -> None:
        actor = User.find(event.conn, event.user_id) if event.user_id else None
        AuditLog.record(event.conn, "queue.failed", actor=actor, target_type="Is", target_id=event.job_id,
                        target_label=event.job, after={"hata": event.error})
        if actor and event.job != "GenerateDocumentJob":
            Notification.send(event.conn, actor.id, "queue.failed", level="hata",
                              title="Arka plan işi başarısız", body=f"{event.job}: {event.error}",
                              data={"job_id": event.job_id})
