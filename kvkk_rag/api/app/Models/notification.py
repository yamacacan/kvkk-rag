"""Uygulama ici bildirim (Laravel database notification karsiligi). Kullaniciya
ozeldir; header'daki zil okunmamis sayisini ve son bildirimleri buradan okur.
Bildirimler dinleyiciler tarafindan (olay -> Notification.send) uretilir."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from .base import Model, now

LEVELS = ("ok", "bilgi", "uyari", "hata")


class Notification(Model):
    table = "notifications"
    fillable = ("user_id", "type", "level", "title", "body", "link", "data", "read_at",
                "created_at", "updated_at")

    @classmethod
    def send(cls, conn: sqlite3.Connection, user_id: int, type: str, title: str, body: str | None = None,
             link: str | None = None, level: str = "bilgi", data: dict[str, Any] | None = None) -> "Notification":
        return cls.create(conn, user_id=user_id, type=type, level=level if level in LEVELS else "bilgi",
                          title=title, body=body, link=link,
                          data=json.dumps(data, ensure_ascii=False, default=str) if data else None)

    @classmethod
    def send_many(cls, conn: sqlite3.Connection, user_ids: Iterable[int], **kw: Any) -> int:
        n = 0
        for uid in set(user_ids):
            cls.send(conn, uid, **kw)
            n += 1
        return n

    @classmethod
    def for_user(cls, conn: sqlite3.Connection, user_id: int, limit: int = 20, only_unread: bool = False) -> list["Notification"]:
        q = cls.query(conn).where("user_id", user_id)
        if only_unread:
            q.where_null("read_at")
        return q.order_by("id", "DESC").limit(limit).get()

    @classmethod
    def unread_count(cls, conn: sqlite3.Connection, user_id: int) -> int:
        return cls.query(conn).where("user_id", user_id).where_null("read_at").count()

    @classmethod
    def mark_all_read(cls, conn: sqlite3.Connection, user_id: int) -> int:
        return cls.query(conn).where("user_id", user_id).where_null("read_at").update(
            {"read_at": now(), "updated_at": now()})

    def mark_read(self, conn: sqlite3.Connection) -> "Notification":
        return self if self.get("read_at") else self.update(conn, read_at=now())

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        if d.get("data"):
            try:
                d["data"] = json.loads(d["data"])
            except ValueError:
                pass
        d["okundu"] = bool(d.get("read_at"))
        return d
