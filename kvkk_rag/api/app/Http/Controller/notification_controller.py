"""Uygulama ici bildirimler (header zili + "Tüm bildirimler" sayfasi). Kullanici
yalnizca kendi bildirimlerini gorur/okur/siler; ek izin gerekmez, oturum yeterlidir."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException

from ....database.connection import get_db
from ...Models.notification import Notification
from ...Models.user import User
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class NotificationController(Controller):
    prefix = "/api/notifications"
    tags = ["bildirimler"]
    middleware = (authenticate,)

    @route("GET", "")
    def index(self, limit: int = 20, offset: int = 0, sadece_okunmamis: bool = False,
              durum: str | None = None, tur: str | None = None, arama: str | None = None,
              user: User = Depends(authenticate), conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # durum: okunmamis | okunmus | None (tumu); tur: bildirim tipi (documents.ready ...)
        q = Notification.query(conn).where("user_id", user.id)
        if sadece_okunmamis or durum == "okunmamis":
            q.where_null("read_at")
        elif durum == "okunmus":
            q.where_not_null("read_at")
        if tur:
            q.where("type", tur)
        if arama:
            q.where_group(lambda g: g.where("title", "LIKE", f"%{arama}%").or_where("body", "LIKE", f"%{arama}%"))
        toplam = q.count()
        limit = max(1, min(limit, 100))
        kayitlar = q.order_by("id", "DESC").limit(limit).offset(max(0, offset)).get()
        turler = [r[0] for r in conn.execute(
            "SELECT DISTINCT type FROM notifications WHERE user_id = ? ORDER BY type", (user.id,))]
        return {"bildirimler": [n.to_dict() for n in kayitlar], "toplam": toplam, "offset": offset, "limit": limit,
                "okunmamis": Notification.unread_count(conn, user.id), "turler": turler}

    @route("GET", "/unread-count")
    def unread(self, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Header zili bunu periyodik sorar; hafif tutulur
        return {"okunmamis": Notification.unread_count(conn, user.id)}

    @route("POST", "/read-all")
    def read_all(self, user: User = Depends(authenticate),
                 conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"okundu": Notification.mark_all_read(conn, user.id)}

    @route("POST", "/clear-read")
    def clear_read(self, user: User = Depends(authenticate),
                   conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Okunmus bildirimleri topluca temizle (okunmamislar kalir)
        return {"silindi": Notification.query(conn).where("user_id", user.id).where_not_null("read_at").delete()}

    def _benim(self, conn: sqlite3.Connection, user: User, nid: int) -> Notification:
        n = self.find_or_fail(Notification.find(conn, nid), "Bildirim bulunamadı")
        if n.user_id != user.id:
            raise HTTPException(403, "Bu bildirim size ait değil.")
        return n

    @route("POST", "/{nid}/read")
    def read(self, nid: int, user: User = Depends(authenticate),
             conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"bildirim": self._benim(conn, user, nid).mark_read(conn).to_dict()}

    @route("POST", "/{nid}/unread")
    def unread_one(self, nid: int, user: User = Depends(authenticate),
                   conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        n = self._benim(conn, user, nid)
        if n.get("read_at"):
            n = n.update(conn, read_at=None)
        return {"bildirim": n.to_dict()}

    @route("DELETE", "/{nid}")
    def destroy(self, nid: int, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        self._benim(conn, user, nid).delete(conn)
        return {"silindi": nid}
