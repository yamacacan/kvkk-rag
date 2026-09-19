"""Sayfa goruntuleme -> denetim gunlugu (page.view). Arayuz her rota degisiminde
POST /api/audit-logs/page-view cagirir: kim, hangi ekrana, ne zaman bakti."""
from __future__ import annotations

from ..Events import PageViewed
from ..Models.audit_log import AuditLog


class LogPageView:
    def handle(self, event: PageViewed) -> None:
        AuditLog.record(event.conn, "page.view", actor=event.user, target_type="Sayfa",
                        target_id=event.name, target_label=event.title or event.path,
                        after={"path": event.path, "name": event.name}, ip=event.ip)
