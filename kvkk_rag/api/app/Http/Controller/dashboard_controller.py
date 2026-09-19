"""Panel (dashboard): kullanicinin izinli oldugu bloklari tek istekte toplar.
Her blok kendi izniyle korunur; izin yoksa blok hic yer almaz."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends

from ....database.connection import get_db
from ...Models.audit_log import AuditLog
from ...Models.department import Department
from ...Models.job import Job
from ...Models.role import Role
from ...Models.user import User
from ...Services.inventory_service import InventoryService
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class DashboardController(Controller):
    prefix = "/api/dashboard"
    tags = ["panel"]
    middleware = (authenticate,)

    @route("GET", "")
    def index(self, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        out: dict[str, Any] = {"kapsam": {}}

        if user.can(conn, "findings.view") or user.can(conn, "inventory.view"):
            modul = "findings" if user.can(conn, "findings.view") else "inventory"
            rows = InventoryService.rows(conn, user, modul, "view")
            ozet = InventoryService.summary(rows)
            out["envanter"] = ozet
            out["kapsam"]["envanter"] = user.scope_for(conn, modul, "view")
            # en riskli faaliyetler (kapsam icinde)
            faaliyet: dict[str, dict[str, int]] = {}
            for r in rows:
                if not r.faaliyet:
                    continue
                f = faaliyet.setdefault(r.faaliyet, {"satir": 0, "bulgu": 0, "kritik": 0})
                f["satir"] += 1
                f["bulgu"] += len(r.bulgular)
                f["kritik"] += sum(1 for b in r.bulgular if b["seviye"] == "kritik")
            out["riskli_faaliyetler"] = [{"faaliyet": k, **v} for k, v in
                                         sorted(faaliyet.items(), key=lambda kv: (-kv[1]["kritik"], -kv[1]["bulgu"]))[:8]]
            # son envanter hareketleri (gorunur satirlar)
            if user.can(conn, "inventory.history"):
                gorunur = {r.satir_no for r in rows}
                hareket = []
                for h in conn.execute("SELECT id, satir_no, islem, zaman, kullanici_id FROM envanter_log ORDER BY id DESC LIMIT 60"):
                    if h["satir_no"] in gorunur or user.is_super(conn):
                        hareket.append(dict(h))
                    if len(hareket) >= 8:
                        break
                kullanicilar = {u.id: u.name for u in User.all(conn)} if hareket else {}
                for h in hareket:
                    h["kullanici"] = kullanicilar.get(h.get("kullanici_id"))
                out["son_hareketler"] = hareket

        if user.can(conn, "users.view"):
            aktif_oturum = conn.execute(
                "SELECT COUNT(*) FROM personal_access_tokens WHERE name = 'refresh' "
                "AND (expires_at IS NULL OR expires_at > strftime('%Y-%m-%dT%H:%M:%S+00:00','now'))").fetchone()[0]
            out["yonetim"] = {
                "kullanici": User.query(conn).count(),
                "aktif_kullanici": User.query(conn).where("is_active", 1).count(),
                "rol": Role.query(conn).count(),
                "departman": Department.query(conn).count(),
                "aktif_oturum": int(aktif_oturum),
                "kuyruk": Job.stats(conn),
            }

        if user.can(conn, "audit.view"):
            # Panelde sayfa goruntulemeleri gosterilmez (gunluk sayfasinda tumu var)
            out["denetim_gunlugu"] = [k.to_dict() for k in AuditLog.query(conn).where("action", "!=", "page.view")
                                      .order_by("id", "DESC").limit(8).get()]

        return out
