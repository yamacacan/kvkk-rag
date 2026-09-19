"""Envanter ya da kurum profili degisti -> etkilenen faaliyetlerin belgeleri (Aydinlatma Metni,
Acik Riza Beyani) eski isaretlenir ve kuyrukta yeniden uretilir. Satir bazli degisimde yalnizca
o satirin (eski ve yeni) faaliyeti; ice aktarim ve profil degisiminde tum faaliyetler."""
from __future__ import annotations

import logging

from ....inventory import store as inv_store
from ..Events import EnvanterChanged, KurumProfiliGuncellendi

logger = logging.getLogger("kvkk_rag.api.faaliyet_belgeleri")


class RefreshFaaliyetBelgeleri:
    def handle(self, event: EnvanterChanged | KurumProfiliGuncellendi) -> None:
        from ..Jobs.faaliyet_belgesi_job import FaaliyetBelgeleriTopluJob
        from ..Services.faaliyet_belge_service import FaaliyetBelgeService

        uid = getattr(event.user, "id", None) if getattr(event, "user", None) else None
        if isinstance(event, KurumProfiliGuncellendi) or event.islem == "ice_aktar":
            FaaliyetBelgeleriTopluJob(uid).dispatch(conn=event.conn, user_id=uid)
            return
        if event.islem not in ("olustur", "guncelle", "sil"):
            return
        faaliyetler = set()
        for d in (event.once, event.sonra):
            if d and (d.get("faaliyet") or "").strip():
                faaliyetler.add(d["faaliyet"].strip())
        if event.satir_no is not None and event.islem != "sil":
            r = inv_store.get(event.conn, event.satir_no)
            if r and (r.faaliyet or "").strip():
                faaliyetler.add(r.faaliyet.strip())
        for f in faaliyetler:
            FaaliyetBelgeService.yenile(event.conn, f, user_id=uid)
