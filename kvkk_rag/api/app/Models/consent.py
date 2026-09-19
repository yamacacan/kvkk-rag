"""Acik riza kaydi (consents): ilgili kisinin bir faaliyet icin verdigi / vermedigi /
geri cektigi acik riza. Kapsam eslemesi (Scopable):
  own        -> consents.created_by = user.id
  assigned   -> faaliyeti, kullanicinin sorumlu/denetci oldugu envanter satirlarinda gecen kayitlar
  department -> consents.birim IN (kullanicinin departman adlari)
TC kimlik numarasi listelerde maskelenir (to_dict(mask=True))."""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .base import Model, QueryBuilder
from .department import Department
from .scopable import Scopable
from .user import User

ONAYLANDI, ONAYLANMADI, GERI_CEKILDI = "onaylandi", "onaylanmadi", "geri_cekildi"
DURUMLAR = (ONAYLANDI, ONAYLANMADI, GERI_CEKILDI)
YONTEMLER = ("islak_imza", "elektronik", "eposta", "sms", "sozlu", "diger")
DURUM_ADI = {ONAYLANDI: "Onaylandı", ONAYLANMADI: "Onaylanmadı", GERI_CEKILDI: "Geri Çekildi"}
YONTEM_ADI = {"islak_imza": "Islak imzalı form", "elektronik": "Elektronik onay (web / uygulama)", "eposta": "E-posta",
              "sms": "SMS", "sozlu": "Sözlü / telefon", "diger": "Diğer"}


def tc_gecerli(tc: str) -> bool:
    # 11 hane, ilk hane 0 degil, 10. ve 11. hane kontrol basamaklari
    if not tc or not tc.isdigit() or len(tc) != 11 or tc[0] == "0":
        return False
    h = [int(c) for c in tc]
    tek, cift = sum(h[0:9:2]), sum(h[1:8:2])
    if (tek * 7 - cift) % 10 != h[9]:
        return False
    return sum(h[:10]) % 10 == h[10]


def tc_maskele(tc: str) -> str:
    return f"{tc[:3]}*****{tc[-3:]}" if tc and len(tc) == 11 else "***"


class Consent(Scopable, Model):
    table = "consents"
    module = "consents"
    owner_column = "created_by"
    fillable = ("faaliyet", "birim", "tc_kimlik", "ad", "soyad", "durum", "onay_tarihi", "geri_cekme_tarihi",
                "onay_yontemi", "notlar", "created_by", "updated_by", "created_at", "updated_at")

    # ---- sorgu seviyesi kapsam ----
    @classmethod
    def scope_assigned(cls, query: QueryBuilder, user: User) -> QueryBuilder:
        return query.where_raw(
            "consents.faaliyet IN (SELECT faaliyet FROM envanter WHERE sorumlu_id = ? OR satir_no IN "
            "(SELECT satir_no FROM envanter_denetcileri WHERE user_id = ?))", (user.id, user.id))

    @classmethod
    def scope_for_department(cls, query: QueryBuilder, department_ids: Iterable[int]) -> QueryBuilder:
        ids = list(department_ids)
        if not ids:
            return query.where_raw("0 = 1")
        yer = ", ".join("?" * len(ids))
        return query.where_raw(f"consents.birim IN (SELECT name FROM departments WHERE id IN ({yer}))", ids)

    # ---- kayit seviyesi kapsam ----
    def assigned_to(self, conn: sqlite3.Connection, user: User) -> bool:
        return conn.execute(
            "SELECT 1 FROM envanter WHERE faaliyet = ? AND (sorumlu_id = ? OR satir_no IN "
            "(SELECT satir_no FROM envanter_denetcileri WHERE user_id = ?)) LIMIT 1",
            (self.faaliyet, user.id, user.id)).fetchone() is not None

    def in_departments(self, conn: sqlite3.Connection, department_ids: Iterable[int]) -> bool:
        birim = self.get("birim")
        return bool(birim) and birim in Department.names_for(conn, department_ids)

    @property
    def ad_soyad(self) -> str:
        return f"{self.ad} {self.soyad}".strip()

    @classmethod
    def summary(cls, query: QueryBuilder) -> dict[str, int]:
        # Kapsam uygulanmis sorgu uzerinden durum sayaclari
        sql, params = query.to_sql("durum, COUNT(*)")
        sql = sql.replace("SELECT durum, COUNT(*)", "SELECT durum, COUNT(*)", 1) + " GROUP BY durum"
        out = {d: 0 for d in DURUMLAR}
        for durum, n in query.conn.execute(sql, params):
            out[durum] = int(n)
        out["toplam"] = sum(out[d] for d in DURUMLAR)
        return out

    def to_dict(self, mask: bool = True) -> dict[str, Any]:
        d = super().to_dict()
        d["tc_kimlik_maske"] = tc_maskele(d.get("tc_kimlik") or "")
        if mask:
            d["tc_kimlik"] = d["tc_kimlik_maske"]
        d["ad_soyad"] = self.ad_soyad
        d["durum_adi"] = DURUM_ADI.get(d.get("durum"), d.get("durum"))
        d["onay_yontemi_adi"] = YONTEM_ADI.get(d.get("onay_yontemi") or "", d.get("onay_yontemi"))
        return d
