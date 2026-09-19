"""Acik riza kayitlari (consents). Iki kademe:
  permission="consents.view" ...  -> Spatie izni
  ScopeFilter / authorize          -> kapsam (own / assigned / department / all)
Kayit acilirken faaliyetin birimi envanterden alinir; department kapsamli kullanici yalnizca
kendi birimlerinin faaliyetleri icin kayit acabilir. TC kimlik listede maskelidir."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException, Request

from ....database.connection import get_db
from ...Events import ConsentChanged, dispatch
from ...Models import permission_scope as ps
from ...Models.base import now
from ...Models.consent import DURUM_ADI, DURUMLAR, YONTEM_ADI, Consent
from ...Models.user import User
from ...Services.faaliyet_belge_service import FaaliyetBelgeService
from ...Services.scope_filter import ScopeFilter
from ..Middleware.authenticate import authenticate
from ..Request.consent import ConsentRequest
from .base import Controller, route

MODULE = "consents"


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    return ileri.split(",")[0].strip() if ileri else (request.client.host if request.client else None)


class ConsentController(Controller):
    prefix = "/api/consents"
    tags = ["acik-riza"]
    middleware = (authenticate,)

    @route("GET", "", permission="consents.view")
    def index(self, faaliyet: str | None = None, durum: str | None = None, onay_yontemi: str | None = None,
              arama: str | None = None, limit: int = 50, offset: int = 0,
              user: User = Depends(authenticate), conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        q = ScopeFilter.apply(Consent.query(conn), user, MODULE, "view")
        ozet = Consent.summary(q)
        if faaliyet:
            q.where("faaliyet", faaliyet)
        if durum in DURUMLAR:
            q.where("durum", durum)
        if onay_yontemi:
            q.where("onay_yontemi", onay_yontemi)
        if arama:
            a = f"%{arama.strip()}%"
            q.where_group(lambda g: g.where("ad", "LIKE", a).or_where("soyad", "LIKE", a)
                          .or_where("tc_kimlik", "LIKE", a).or_where("faaliyet", "LIKE", a).or_where("notlar", "LIKE", a))
        toplam = q.count()
        kayitlar = q.order_by("id", "DESC").limit(max(1, min(limit, 200))).offset(max(0, offset)).get()
        faaliyetler = [r[0] for r in conn.execute("SELECT DISTINCT faaliyet FROM consents ORDER BY faaliyet")]
        return {"kayitlar": [c.to_dict() for c in kayitlar], "toplam": toplam, "offset": offset, "limit": limit,
                "ozet": ozet, "faaliyetler": faaliyetler, "kapsam": q.scope_applied,
                "durumlar": DURUM_ADI, "yontemler": YONTEM_ADI}

    @route("GET", "/faaliyetler", permission="consents.view")
    def faaliyetler(self, user: User = Depends(authenticate),
                    conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # "Açık Rıza" secimi: kullanicinin gorebildigi envanter faaliyetleri (+ beyan belgesi durumu)
        from ...Models.faaliyet_belgesi import FaaliyetBelgesi
        f = FaaliyetBelgeService.kullanici_faaliyetleri(conn, user)
        belgeler = FaaliyetBelgesi.for_faaliyetler(conn, list(f))
        out = []
        for ad, o in sorted(f.items(), key=lambda kv: kv[0].casefold()):
            b = belgeler.get((ad, "acik_riza"))
            out.append({**o, "beyan": {"id": b.id, "durum": b.durum, "indirilebilir": b.ready} if b else None})
        return {"faaliyetler": out}

    def _birim_dogrula(self, conn: sqlite3.Connection, user: User, faaliyet: str, action: str) -> str:
        # Faaliyetin birimi envanterden; department kapsaminda kendi birimi olmali
        f = FaaliyetBelgeService.kullanici_faaliyetleri(conn, user).get(faaliyet)
        birim = f["birim"] if f else FaaliyetBelgeService.birim(FaaliyetBelgeService.faaliyet_satirlari(conn, faaliyet))
        if user.scope_for(conn, MODULE, action) == ps.DEPARTMENT and birim not in user.department_names(conn):
            raise HTTPException(403, "Yalnızca kendi biriminizin faaliyetleri için açık rıza kaydı açabilirsiniz.")
        return birim

    @route("POST", "", permission="consents.create")
    def store(self, req: ConsentRequest, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        self.authorize(conn, user, MODULE, "create")
        birim = self._birim_dogrula(conn, user, req.faaliyet, "create")
        veri = req.model_dump()
        if veri["durum"] == "onaylandi" and not veri.get("onay_tarihi"):
            veri["onay_tarihi"] = now()
        c = Consent.create(conn, **veri, birim=birim, created_by=user.id, updated_by=user.id)
        dispatch(ConsentChanged("olustur", c, user, conn, sonra=c.to_dict(), ip=_ip(request)))
        return {"kayit": c.to_dict(mask=False)}

    @route("GET", "/{cid}", permission="consents.view")
    def show(self, cid: int, user: User = Depends(authenticate),
             conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        c = self.find_or_fail(Consent.find(conn, cid), "Açık rıza kaydı bulunamadı")
        self.authorize(conn, user, MODULE, "view", c)
        return {"kayit": c.to_dict(mask=False)}

    @route("PATCH", "/{cid}", permission="consents.update")
    def update(self, cid: int, req: ConsentRequest, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        c = self.find_or_fail(Consent.find(conn, cid), "Açık rıza kaydı bulunamadı")
        self.authorize(conn, user, MODULE, "update", c)
        once = c.to_dict()
        birim = c.get("birim") if req.faaliyet == c.faaliyet else self._birim_dogrula(conn, user, req.faaliyet, "update")
        veri = req.model_dump()
        if veri["durum"] == "geri_cekildi" and not once.get("geri_cekme_tarihi") and not veri.get("geri_cekme_tarihi"):
            veri["geri_cekme_tarihi"] = now()
        c.update(conn, **veri, birim=birim, updated_by=user.id)
        sonra = c.to_dict()
        degisen = {k: sonra[k] for k in veri if once.get(k) != sonra.get(k)}
        dispatch(ConsentChanged("guncelle", c, user, conn, once={k: once.get(k) for k in degisen}, sonra=degisen, ip=_ip(request)))
        return {"kayit": c.to_dict(mask=False)}

    @route("DELETE", "/{cid}", permission="consents.delete")
    def destroy(self, cid: int, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        c = self.find_or_fail(Consent.find(conn, cid), "Açık rıza kaydı bulunamadı")
        self.authorize(conn, user, MODULE, "delete", c)
        once = c.to_dict()
        c.delete(conn)
        dispatch(ConsentChanged("sil", c, user, conn, once=once, ip=_ip(request)))
        return {"silindi": cid}
