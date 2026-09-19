"""Arka planda uretilen uyum belgesi. Istek aninda 'kuyrukta' olarak acilir;
GenerateDocumentJob dosyayi diske yazip kaydi 'hazir' (ya da 'hata') yapar.
Dosyalar DATA_DIR/index/belgeler altinda; kayit silinince dosya da silinir."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from ....config import settings
from .base import Model

KUYRUKTA, URETILIYOR, HAZIR, HATA = "kuyrukta", "uretiliyor", "hazir", "hata"
MIME = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "zip": "application/zip",
}


def belge_dizini() -> Path:
    d = settings.INDEX_DIR / "belgeler"
    d.mkdir(parents=True, exist_ok=True)
    return d


class GeneratedDocument(Model):
    table = "generated_documents"
    fillable = ("user_id", "job_id", "sablon", "sablon_adi", "tur", "durum", "istek", "ad", "dosya", "boyut",
                "kalan", "yapay_zeka", "uretilen", "hatalar", "hata", "satir", "created_at", "updated_at")

    @property
    def request_data(self) -> dict[str, Any]:
        try:
            return json.loads(self.get("istek") or "{}")
        except ValueError:
            return {}

    @property
    def mime(self) -> str:
        return MIME.get(self.get("tur") or "docx", "application/octet-stream")

    @property
    def path(self) -> Path | None:
        return Path(self.dosya) if self.get("dosya") else None

    @property
    def ready(self) -> bool:
        p = self.path
        return self.get("durum") == HAZIR and p is not None and p.exists()

    @classmethod
    def open(cls, conn: sqlite3.Connection, user_id: int, sablon: str, sablon_adi: str, tur: str,
             istek: dict[str, Any]) -> "GeneratedDocument":
        return cls.create(conn, user_id=user_id, sablon=sablon, sablon_adi=sablon_adi, tur=tur, durum=KUYRUKTA,
                          istek=json.dumps(istek, ensure_ascii=False, default=str))

    @classmethod
    def for_user(cls, conn: sqlite3.Connection, user_id: int, limit: int = 30) -> list["GeneratedDocument"]:
        return cls.query(conn).where("user_id", user_id).order_by("id", "DESC").limit(limit).get()

    @classmethod
    def pending_count(cls, conn: sqlite3.Connection, user_id: int) -> int:
        return cls.query(conn).where("user_id", user_id).where_in("durum", (KUYRUKTA, URETILIYOR)).count()

    def store_file(self, conn: sqlite3.Connection, icerik: bytes, ad: str, **alanlar: Any) -> "GeneratedDocument":
        # Dosya adi: {id}_{ad}; ayni is iki kez calisirsa ustune yazar (idempotent)
        yol = belge_dizini() / f"{self.id}_{ad}"
        yol.write_bytes(icerik)
        return self.update(conn, durum=HAZIR, ad=ad, dosya=str(yol), boyut=len(icerik), hata=None, **alanlar)

    def fail(self, conn: sqlite3.Connection, hata: str) -> "GeneratedDocument":
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
        for k in ("kalan", "yapay_zeka", "hatalar"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except ValueError:
                    d[k] = []
            else:
                d[k] = []
        d.pop("dosya", None)  # sunucu yolu arayuze gitmez
        d["indirilebilir"] = self.ready
        return d
