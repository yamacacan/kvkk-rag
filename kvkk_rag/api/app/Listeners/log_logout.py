from __future__ import annotations

from ..Events import Logout
from ..Models.audit_log import AuditLog


class LogLogout:
    def handle(self, event: Logout) -> None:
        AuditLog.record(event.conn, "auth.logout", actor=event.user, target=event.user, ip=event.ip)
