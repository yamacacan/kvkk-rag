"""Faaliyet belgeleri: envanterdeki her faaliyet icin Aydinlatma Metni ve Acik Riza Beyani.

Kaynak envanter (satir bazinda) ya da kurum profili degisince ilgili faaliyetin kayitlari
'eski' olur ve FaaliyetBelgesiJob kuyruga yazilir (EnvanterChanged / KurumProfiliGuncellendi
dinleyicisi). Is, olgularin parmak izi degismediyse uretimi atlar; degistiyse belgeyi
yeniden uretir. Uretim sistem adina (kapsamsiz, tum satirlar) yapilir; listeleme ve
indirme kullanicinin documents.view kapsamindaki faaliyetlerle sinirlidir."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from typing import Any

from ....compliance import generate as comp_generate
from ....compliance import store as comp_store
from ....inventory import store as inv_store
from ....inventory.loader import InventoryRow
from ..Models.faaliyet_belgesi import ESKI, GUNCEL, HATA, KUYRUKTA, URETILIYOR, FaaliyetBelgesi
from ..Models.job import QUEUED, Job as JobRow
from ..Models.user import User

logger = logging.getLogger("kvkk_rag.api.faaliyet_belgeleri")

SABLONLAR = tuple(sorted(comp_generate.FAALIYET_BAZLI))  # ('acik_riza', 'aydinlatma')
PROFIL_ALANLARI = ("kurum", "adres", "web_adres", "cagri_merkezi")


class FaaliyetBelgeService:
    # ---- olgular ----
    @staticmethod
    def faaliyet_satirlari(conn: sqlite3.Connection, faaliyet: str) -> list[InventoryRow]:
        return [r for r in inv_store.all_rows(conn) if (r.faaliyet or "").strip() == faaliyet]

    @staticmethod
    def parmak_izi(rows: list[InventoryRow], profil: dict[str, Any]) -> str:
        olgular = {
            "profil": {k: profil.get(k) or "" for k in PROFIL_ALANLARI},
            "satirlar": sorted((json.dumps({a: getattr(r, a, None) for a in inv_store.ALANLAR}, ensure_ascii=False, sort_keys=True)
                                for r in rows)),
        }
        return hashlib.sha1(json.dumps(olgular, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def birim(rows: list[InventoryRow]) -> str:
        sayac: dict[str, int] = {}
        for r in rows:
            b = (r.birim or "").strip()
            if b:
                sayac[b] = sayac.get(b, 0) + 1
        return max(sayac, key=sayac.get) if sayac else ""

    # ---- kuyruk ----
    @staticmethod
    def kuyrukta_mi(conn: sqlite3.Connection, faaliyet: str, sablon: str) -> bool:
        from ..Jobs.faaliyet_belgesi_job import FaaliyetBelgesiJob
        payload = json.dumps({"faaliyet": faaliyet, "sablon": sablon}, ensure_ascii=False)
        return JobRow.query(conn).where("job", FaaliyetBelgesiJob.path()).where("payload", payload) \
            .where_in("status", (QUEUED, "running")).exists()

    @classmethod
    def yenile(cls, conn: sqlite3.Connection, faaliyet: str, sablonlar: tuple[str, ...] = SABLONLAR,
               user_id: int | None = None) -> int:
        """Faaliyetin belgelerini 'eski' isaretler ve (kuyrukta yoksa) uretim isini kuyruga yazar."""
        from ..Jobs.faaliyet_belgesi_job import FaaliyetBelgesiJob
        n = 0
        for sablon in sablonlar:
            if sablon not in comp_generate.SABLONLAR:
                continue
            kayit = FaaliyetBelgesi.find_for(conn, faaliyet, sablon)
            if kayit is None:
                FaaliyetBelgesi.create(conn, faaliyet=faaliyet, sablon=sablon, durum=KUYRUKTA)
            elif kayit.durum in (GUNCEL, HATA):
                kayit.update(conn, durum=ESKI)
            if not cls.kuyrukta_mi(conn, faaliyet, sablon):
                FaaliyetBelgesiJob(faaliyet, sablon).dispatch(conn=conn, user_id=user_id)
                n += 1
        return n

    @classmethod
    def tumunu_yenile(cls, conn: sqlite3.Connection, user_id: int | None = None) -> int:
        faaliyetler = sorted({(r.faaliyet or "").strip() for r in inv_store.all_rows(conn) if (r.faaliyet or "").strip()})
        # envanterden silinmis faaliyetlerin kayitlari temizlenir
        for b in FaaliyetBelgesi.all(conn):
            if b.faaliyet not in faaliyetler:
                b.delete(conn)
        return sum(cls.yenile(conn, f, user_id=user_id) for f in faaliyetler)

    # ---- uretim (is icinden) ----
    @classmethod
    def uret(cls, conn: sqlite3.Connection, faaliyet: str, sablon: str, zorla: bool = False) -> tuple[str, FaaliyetBelgesi | None]:
        """-> (sonuc, kayit). sonuc: 'uretildi' | 'guncel' | 'silindi' | 'hata'."""
        from ....compliance import profile as comp_profile
        from datetime import date

        rows = cls.faaliyet_satirlari(conn, faaliyet)
        kayit = FaaliyetBelgesi.find_for(conn, faaliyet, sablon)
        if not rows:
            if kayit is not None:
                kayit.delete(conn)
            return "silindi", None
        if kayit is None:
            kayit = FaaliyetBelgesi.create(conn, faaliyet=faaliyet, sablon=sablon, durum=KUYRUKTA)
        profil = comp_store.get(conn)
        iz = cls.parmak_izi(rows, profil)
        if not zorla and kayit.get("parmak_izi") == iz and kayit.ready:
            if kayit.durum != GUNCEL:
                kayit.update(conn, durum=GUNCEL)
            return "guncel", kayit
        kayit.update(conn, durum=URETILIYOR, birim=cls.birim(rows))
        try:
            p = comp_profile.from_inventory(rows, kurum=profil.get("kurum") or "", adres=profil.get("adres") or "",
                                            web_adres=profil.get("web_adres") or "", faaliyet=faaliyet)
            p.cagri_merkezi = profil.get("cagri_merkezi") or ""
            p.belge_tarihi = f"{date.today():%d.%m.%Y}"
            icerik, kalan, ad, _kaynak = comp_generate.uret(sablon, p, rows, None)
        except Exception as e:  # noqa: BLE001
            kayit.fail(conn, f"{type(e).__name__}: {e}")
            return "hata", kayit
        kayit = kayit.store_file(conn, icerik, ad, iz, satir=len(rows), kalan=json.dumps(kalan, ensure_ascii=False))
        return "uretildi", kayit

    # ---- listeleme (kullanici kapsami) ----
    @staticmethod
    def kullanici_faaliyetleri(conn: sqlite3.Connection, user: User) -> dict[str, dict[str, Any]]:
        from .inventory_service import InventoryService
        rows = InventoryService.rows(conn, user, "documents", "view")
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            f = (r.faaliyet or "").strip()
            if not f:
                continue
            o = out.setdefault(f, {"faaliyet": f, "satir": 0, "birimler": {}, "bulgu": 0})
            o["satir"] += 1
            o["bulgu"] += len(r.bulgular or [])
            b = (r.birim or "").strip()
            if b:
                o["birimler"][b] = o["birimler"].get(b, 0) + 1
        for o in out.values():
            o["birim"] = max(o["birimler"], key=o["birimler"].get) if o["birimler"] else ""
            o.pop("birimler")
        return out

    @classmethod
    def liste(cls, conn: sqlite3.Connection, user: User) -> dict[str, Any]:
        faaliyetler = cls.kullanici_faaliyetleri(conn, user)
        kayitlar = FaaliyetBelgesi.for_faaliyetler(conn, list(faaliyetler))
        # eksik kayitlar tembel olusturulur ve kuyruga alinir
        for f in faaliyetler:
            if any((f, s) not in kayitlar for s in SABLONLAR):
                cls.yenile(conn, f)
        kayitlar = FaaliyetBelgesi.for_faaliyetler(conn, list(faaliyetler))
        ozet = {"faaliyet": len(faaliyetler), "guncel": 0, "eski": 0, "kuyrukta": 0, "hata": 0}
        satirlar = []
        for f, o in sorted(faaliyetler.items(), key=lambda kv: kv[0].casefold()):
            belgeler = {}
            for s in SABLONLAR:
                b = kayitlar.get((f, s))
                belgeler[s] = b.to_dict() if b else None
                if b:
                    d = b.durum
                    ozet["guncel" if d == GUNCEL else "eski" if d == ESKI else "hata" if d == HATA else "kuyrukta"] += 1
            satirlar.append({**o, "belgeler": belgeler})
        ozet["bekleyen"] = ozet["kuyrukta"]
        return {"faaliyetler": satirlar, "ozet": ozet, "sablonlar": {s: comp_generate.BELGE_ADI[s] for s in SABLONLAR}}
