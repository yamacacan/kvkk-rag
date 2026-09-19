"""Envanter arka plan islemi (envanter_islemleri). Istek aninda 'kuyrukta' acilir;
ilgili is (Export/Import/ReindexEnvanterJob) calistirir, 'tamamlandi' ya da 'hata'
yapar. Disa aktarimin ciktisi ve ice aktarimin yuklenen dosyasi diskte tutulur."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ....config import settings
from .base import Model

DISA_AKTAR, ICE_AKTAR, YENIDEN_INDEKSLE = "disa_aktar", "ice_aktar", "yeniden_indeksle"
KUYRUKTA, CALISIYOR, TAMAMLANDI, HATA = "kuyrukta", "calisiyor", "tamamlandi", "hata"
TUR_ADI = {DISA_AKTAR: "Excel dışa aktarım", ICE_AKTAR: "Excel içe aktarım", YENIDEN_INDEKSLE: "Vektör indeksi"}
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def islem_dizini() -> Path:
    d = settings.INDEX_DIR / "envanter_islemleri"
    d.mkdir(parents=True, exist_ok=True)
    return d


class EnvanterIslemi(Model):
    table = "envanter_islemleri"
    fillable = ("user_id", "job_id", "tur", "durum", "istek", "ad", "dosya", "boyut", "sonuc", "hata",
                "created_at", "updated_at")

    @property
    def request_data(self) -> dict[str, Any]:
        try:
            return json.loads(self.get("istek") or "{}")
        except ValueError:
            return {}

    @property
    def result(self) -> dict[str, Any]:
        try:
            return json.loads(self.get("sonuc") or "{}")
        except ValueError:
            return {}

    @property
    def path(self) -> Path | None:
        return Path(self.dosya) if self.get("dosya") else None

    @property
    def downloadable(self) -> bool:
        p = self.path
        return self.tur == DISA_AKTAR and self.durum == TAMAMLANDI and p is not None and p.exists()

    @classmethod
    def open(cls, conn: sqlite3.Connection, user_id: int, tur: str, istek: dict[str, Any],
             ad: str | None = None, dosya: str | None = None, boyut: int | None = None) -> "EnvanterIslemi":
        return cls.create(conn, user_id=user_id, tur=tur, durum=KUYRUKTA, ad=ad, dosya=dosya, boyut=boyut,
                          istek=json.dumps(istek, ensure_ascii=False, default=str))

    @classmethod
    def for_user(cls, conn: sqlite3.Connection, user_id: int, limit: int = 30) -> list["EnvanterIslemi"]:
        return cls.query(conn).where("user_id", user_id).order_by("id", "DESC").limit(limit).get()

    @classmethod
    def pending_count(cls, conn: sqlite3.Connection, user_id: int) -> int:
        return cls.query(conn).where("user_id", user_id).where_in("durum", (KUYRUKTA, CALISIYOR)).count()

    def start(self, conn: sqlite3.Connection) -> "EnvanterIslemi":
        return self.update(conn, durum=CALISIYOR)

    def finish(self, conn: sqlite3.Connection, sonuc: dict[str, Any] | None = None, **alanlar: Any) -> "EnvanterIslemi":
        return self.update(conn, durum=TAMAMLANDI, hata=None,
                           sonuc=json.dumps(sonuc or {}, ensure_ascii=False, default=str), **alanlar)

    def store_output(self, conn: sqlite3.Connection, icerik: bytes, ad: str, sonuc: dict[str, Any] | None = None) -> "EnvanterIslemi":
        # Cikti dosyasi: {id}_{ad}; ayni is iki kez calisirsa ustune yazar (idempotent)
        yol = islem_dizini() / f"{self.id}_{ad}"
        yol.write_bytes(icerik)
        return self.finish(conn, sonuc, ad=ad, dosya=str(yol), boyut=len(icerik))

    def fail(self, conn: sqlite3.Connection, hata: str) -> "EnvanterIslemi":
        return self.update(conn, durum=HATA, hata=hata[:1000])

    def delete(self, conn: sqlite3.Connection) -> bool:
        p = self.path
        ok = super().delete(conn)
        if ok and p and p.exists():
            try:
                os.remove(p)
            except OSError:
                pass
        return ok

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["istek"] = self.request_data
        d["sonuc"] = self.result
        d["tur_adi"] = TUR_ADI.get(self.tur, self.tur)
        d.pop("dosya", None)  # sunucu yolu arayuze gitmez
        d["indirilebilir"] = self.downloadable
        return d
