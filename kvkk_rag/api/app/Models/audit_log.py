"""Denetim gunlugu (audit trail): kim, ne zaman, neyi degistirdi. Yonetim ve
kimlik islemleri buraya yazilir; envanter satir degisiklikleri envanter_log'da."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .base import Model


class AuditLog(Model):
    table = "audit_logs"
    fillable = ("user_id", "user_email", "action", "target_type", "target_id", "target_label",
                "before", "after", "ip", "created_at")
    timestamps = False

    @classmethod
    def record(cls, conn: sqlite3.Connection, action: str, actor: Any | None = None,
               target: Any | None = None, target_type: str | None = None, target_id: Any = None,
               target_label: str | None = None, before: Any = None, after: Any = None,
               ip: str | None = None) -> "AuditLog":
        from .base import now
        if target is not None:
            target_type = target_type or type(target).__name__
            target_id = target_id if target_id is not None else target.key
            target_label = target_label or target.get("name") or target.get("email") or str(target.key)
        return cls.create(
            conn, user_id=getattr(actor, "id", None), user_email=getattr(actor, "email", None),
            action=action, target_type=target_type,
            target_id=None if target_id is None else str(target_id), target_label=target_label,
            before=None if before is None else json.dumps(before, ensure_ascii=False, default=str),
            after=None if after is None else json.dumps(after, ensure_ascii=False, default=str),
            ip=ip, created_at=now())

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        for k in ("before", "after"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    pass
        return d
