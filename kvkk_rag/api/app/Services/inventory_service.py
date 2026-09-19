"""Envanter is mantigi: kapsam filtreli okuma, denetim, filtreleme, ozet, yazma.
Controller'lar yalnizca HTTP'yi konusur; SQL ve kapsam kararlari burada."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from ....inventory import audit as inv_audit
from ....inventory import store as inv_store
from ....inventory.loader import InventoryRow
from ..Events import EnvanterChanged, dispatch
from ..Models.base import QueryBuilder
from ..Models.envanter import Envanter
from ..Models.user import User
from .scope_filter import ScopeFilter

logger = logging.getLogger("kvkk_rag.api.inventory")

MODULE = "inventory"


class InventoryService:
    # ---- okuma ----
    @staticmethod
    def ensure_imported(conn: sqlite3.Connection, user: User | None = None, force: bool = False) -> int:
        # Kaynak SQLite; ilk calistirmada xlsx bir kez ice aktarilir. Dosya (veya
        # openpyxl) yoksa envanter bos baslar (yeni kurulum), hata degil.
        try:
            n = inv_store.import_xlsx(conn, force=force)
        except (FileNotFoundError, ImportError) as e:
            logger.warning("Envanter xlsx alınamadı, boş envanterle devam: %s", e)
            return 0
        if n:
            # Her veri aktarimi denetim gunlugune (aktor yoksa sistem)
            dispatch(EnvanterChanged("ice_aktar", conn, user=user, adet=n,
                                     etiket=f"veri_envanteri.xlsx · {n} satır"))
        return n

    @staticmethod
    def visible_query(conn: sqlite3.Connection, user: User, module: str = MODULE,
                      action: str = "view") -> QueryBuilder:
        # Sorgu seviyesi filtreleme: kapsam SQL kosulu olarak eklenir
        return ScopeFilter.apply(Envanter.query(conn), user, module, action)

    @classmethod
    def rows(cls, conn: sqlite3.Connection, user: User, module: str = MODULE,
             action: str = "view") -> list[InventoryRow]:
        cls.ensure_imported(conn)
        rows = Envanter.rows(cls.visible_query(conn, user, module, action))
        inv_audit.audit(rows)
        return rows

    @classmethod
    def visible_ids(cls, conn: sqlite3.Connection, user: User, module: str = MODULE,
                    action: str = "view") -> set[int] | None:
        # None -> kisit yok (all). Vektor aramasi gibi SQL disi kaynaklari suzmek icin.
        q = cls.visible_query(conn, user, module, action)
        if q.scope_applied == "all":
            return None
        return set(q.pluck("satir_no"))

    @staticmethod
    def filter(rows: list[InventoryRow], birim: str | None = None, faaliyet: str | None = None,
               veri_kategorisi: str | None = None, hukuki_sebep: str | None = None,
               seviye: str | None = None, sadece_bulgulu: bool = False,
               arama: str | None = None) -> list[InventoryRow]:
        def ok(r: InventoryRow) -> bool:
            for deger, alan in ((birim, r.birim), (faaliyet, r.faaliyet),
                                (veri_kategorisi, r.veri_kategorisi),
                                (hukuki_sebep, r.hukuki_sebep)):
                if deger and deger.lower() not in (alan or "").lower():
                    return False
            if sadece_bulgulu and not r.bulgular:
                return False
            if seviye and not any(b["seviye"] == seviye for b in r.bulgular):
                return False
            if arama:
                hay = " ".join(str(v or "") for v in r.to_dict().values()).lower()
                if arama.lower() not in hay:
                    return False
            return True

        return [r for r in rows if ok(r)]

    @staticmethod
    def summary(rows: list[InventoryRow]) -> dict[str, Any]:
        sev: dict[str, int] = {}
        kod: dict[str, int] = {}
        for r in rows:
            for b in r.bulgular:
                sev[b["seviye"]] = sev.get(b["seviye"], 0) + 1
                kod[b["kod"]] = kod.get(b["kod"], 0) + 1
        temiz = sum(1 for r in rows if not r.bulgular)

        def dagilim(alan: str, n: int = 12) -> list[dict[str, Any]]:
            c: dict[str, int] = {}
            for r in rows:
                v = getattr(r, alan)
                if v:
                    c[v] = c.get(v, 0) + 1
            return [{"deger": k, "adet": v}
                    for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:n]]

        return {
            "satir": len(rows), "bulgu": sum(len(r.bulgular) for r in rows),
            "temiz_satir": temiz,
            "uyum_orani": round(temiz / len(rows), 4) if rows else 0.0,
            "seviye": sev, "kod": kod,
            "birim": dagilim("birim"), "faaliyet": dagilim("faaliyet"),
            "veri_kategorisi": dagilim("veri_kategorisi", 20),
        }

    @staticmethod
    def find(conn: sqlite3.Connection, satir_no: int) -> Envanter | None:
        return Envanter.find(conn, satir_no)

    # ---- yazma (log + vektor indeksi inventory.store'da) ----
    @classmethod
    def create(cls, conn: sqlite3.Connection, user: User, veri: dict[str, Any],
               ip: str | None = None) -> tuple[int, InventoryRow]:
        cls.ensure_imported(conn, user)
        satir_no = inv_store.create(conn, veri, meta={"created_by": user.id}, kullanici_id=user.id)
        dispatch(EnvanterChanged("olustur", conn, user=user, satir_no=satir_no, sonra=dict(veri), ip=ip))
        return satir_no, inv_store.get(conn, satir_no)

    @staticmethod
    def update(conn: sqlite3.Connection, user: User, satir_no: int,
               veri: dict[str, Any], ip: str | None = None) -> InventoryRow | None:
        mevcut = inv_store.get(conn, satir_no)
        row = inv_store.update(conn, satir_no, veri, kullanici_id=user.id)
        if row is not None and mevcut is not None:
            once = {k: getattr(mevcut, k, None) for k in veri}
            degisen = {k: v for k, v in veri.items() if once.get(k) != v}
            if degisen:
                dispatch(EnvanterChanged("guncelle", conn, user=user, satir_no=satir_no,
                                         once={k: once[k] for k in degisen}, sonra=degisen, ip=ip))
        return row

    @staticmethod
    def delete(conn: sqlite3.Connection, user: User, satir_no: int, ip: str | None = None) -> bool:
        mevcut = inv_store.get(conn, satir_no)
        ok = inv_store.delete(conn, satir_no, kullanici_id=user.id)
        if ok:
            dispatch(EnvanterChanged("sil", conn, user=user, satir_no=satir_no,
                                     once=mevcut.to_dict() if mevcut else None, ip=ip))
        return ok

    @staticmethod
    def audit_row(row: InventoryRow) -> list[dict[str, Any]]:
        return [b.to_dict() for b in inv_audit.audit_row(row)]

    @staticmethod
    def history(conn: sqlite3.Connection, satir_no: int) -> list[dict[str, Any]]:
        return inv_store.history(conn, satir_no)

    @staticmethod
    def distinct(conn: sqlite3.Connection, alan: str) -> list[str]:
        return inv_store.distinct(conn, alan)
