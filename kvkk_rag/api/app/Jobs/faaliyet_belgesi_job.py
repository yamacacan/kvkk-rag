"""Faaliyet belgesi uretimi (kuyrukta). Envanter/profil degisince dinleyici bu isi kuyruga
yazar; is, olgularin parmak izi degismemisse uretimi atlar (idempotent)."""
from __future__ import annotations

import logging

from ...database.connection import connect
from ..Events import FaaliyetBelgesiYenilendi, dispatch
from .base import Job, ShouldQueue

logger = logging.getLogger("kvkk_rag.api.jobs")


class FaaliyetBelgesiJob(Job, ShouldQueue):
    queue = "documents"
    max_attempts = 1

    def __init__(self, faaliyet: str, sablon: str) -> None:
        self.faaliyet, self.sablon = faaliyet, sablon

    def handle(self) -> None:
        from ..Services.faaliyet_belge_service import FaaliyetBelgeService

        conn = connect()
        try:
            sonuc, kayit = FaaliyetBelgeService.uret(conn, self.faaliyet, self.sablon)
            logger.info("Faaliyet belgesi %s/%s: %s", self.faaliyet, self.sablon, sonuc)
            if sonuc in ("uretildi", "hata") and kayit is not None:
                dispatch(FaaliyetBelgesiYenilendi(belge=kayit, sonuc=sonuc, conn=conn))
            if sonuc == "hata" and kayit is not None:
                raise RuntimeError(kayit.hata or "belge üretilemedi")
        finally:
            conn.close()


class FaaliyetBelgeleriTopluJob(Job, ShouldQueue):
    """Tum faaliyetler icin yenileme (ice aktarim / kurum profili degisimi / elle 'tumunu yenile')."""
    queue = "documents"
    max_attempts = 1

    def __init__(self, user_id: int | None = None) -> None:
        self.user_id = user_id

    def handle(self) -> None:
        from ..Services.faaliyet_belge_service import FaaliyetBelgeService

        conn = connect()
        try:
            n = FaaliyetBelgeService.tumunu_yenile(conn, user_id=self.user_id)
            logger.info("Faaliyet belgeleri toplu yenileme: %s is kuyruga alindi", n)
        finally:
            conn.close()
