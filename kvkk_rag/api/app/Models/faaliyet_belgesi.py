"""Faaliyet belgesi: envanterdeki her faaliyet icin sablon basina (aydinlatma, acik_riza)
bir kayit. Envanter ya da kurum profili degisince kayit 'eski' olur ve kuyruktaki is
yeniden uretir; parmak izi ayni ise uretim atlanir. Dosyalar DATA_DIR/index/faaliyet_belgeleri."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ....config import settings
from .base import Model, now

KUYRUKTA, URETILIYOR, GUNCEL, ESKI, HATA = "kuyrukta", "uretiliyor", "guncel", "eski", "hata"


def belge_dizini() -> Path:
    d = settings.INDEX_DIR / "faaliyet_belgeleri"
    d.mkdir(parents=True, exist_ok=True)
    return d


class FaaliyetBelgesi(Model):
    table = "faaliyet_belgeleri"
    fillable = ("faaliyet", "sablon", "birim", "durum", "parmak_izi", "ad", "dosya", "boyut", "satir", "kalan",
                "hata", "son_uretim", "created_at", "updated_at")

    @property
    def path(self) -> Path | None:
        return Path(self.dosya) if self.get("dosya") else None

    @property
    def ready(self) -> bool:
        p = self.path
        return self.get("durum") in (GUNCEL, ESKI) and p is not None and p.exists()

    @classmethod
    def find_for(cls, conn: sqlite3.Connection, faaliyet: str, sablon: str) -> "FaaliyetBelgesi | None":
        return cls.query(conn).where("faaliyet", faaliyet).where("sablon", sablon).first()

    @classmethod
    def for_faaliyetler(cls, conn: sqlite3.Connection, faaliyetler: list[str]) -> dict[tuple[str, str], "FaaliyetBelgesi"]:
        if not faaliyetler:
            return {}
        return {(b.faaliyet, b.sablon): b for b in cls.query(conn).where_in("faaliyet", faaliyetler).get()}

    @classmethod
    def mark_stale(cls, conn: sqlite3.Connection, faaliyet: str | None = None) -> int:
        # None -> tum kayitlar (kurum profili degisti); uretimi suren kayitlara dokunulmaz
        q = cls.query(conn).where_in("durum", (GUNCEL, HATA))
        if faaliyet is not None:
            q.where("faaliyet", faaliyet)
        return q.update({"durum": ESKI, "updated_at": now()})

    def store_file(self, conn: sqlite3.Connection, icerik: bytes, ad: str, parmak_izi: str, **alanlar: Any) -> "FaaliyetBelgesi":
        yol = belge_dizini() / f"{self.id}_{self.sablon}.docx"
        yol.write_bytes(icerik)
        return self.update(conn, durum=GUNCEL, ad=ad, dosya=str(yol), boyut=len(icerik), parmak_izi=parmak_izi,
                           hata=None, son_uretim=now(), **alanlar)

    def fail(self, conn: sqlite3.Connection, hata: str) -> "FaaliyetBelgesi":
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
        try:
            d["kalan"] = json.loads(d["kalan"]) if d.get("kalan") else []
        except ValueError:
            d["kalan"] = []
        d.pop("dosya", None)
        d.pop("parmak_izi", None)
        d["indirilebilir"] = self.ready
        return d
