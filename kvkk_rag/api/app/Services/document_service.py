"""Uyum belgesi uretimi: kurum profili + kapsam filtreli envanter -> docx / zip."""
from __future__ import annotations

import functools
import io
import logging
import re
import zipfile
from datetime import date
from typing import Any

from ....compliance import generate as comp_generate
from ....compliance import profile as comp_profile
from ....compliance import sections as comp_sections
from ....inventory.loader import InventoryRow
from ..Http.Request.document import DocumentRequest

logger = logging.getLogger("kvkk_rag.api.documents")


class DocumentService:
    @staticmethod
    def profile(req: DocumentRequest, rows: list[InventoryRow]):
        # faaliyet basliktir, filtre degil; kapsam daraltma faaliyet_filtresi ile yapilir
        p = comp_profile.from_inventory(
            rows, kurum=req.kurum, adres=req.adres, web_adres=req.web_adres,
            birim=req.birim, faaliyet=req.faaliyet_filtresi)
        p.faaliyet = req.faaliyet
        p.cagri_merkezi = req.cagri_merkezi
        p.veri_isleyen = req.veri_isleyen
        p.sozlesme_adi = req.sozlesme_adi
        p.sozlesme_tarihi = req.sozlesme_tarihi
        p.protokol_tarihi = req.protokol_tarihi or f"{date.today():%d.%m.%Y}"
        p.belge_tarihi = f"{date.today():%d.%m.%Y}"
        return p

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def llm():
        # Sablonun yapay zeka ile yazilan bolumleri icin. Saglayici yoksa None
        # doner; sections.py ayni olgulardan deterministik metne duser.
        from ....llm.factory import get_llm
        try:
            return get_llm()
        except Exception as e:  # noqa: BLE001
            logger.warning("Belge üretimi LLM'siz çalışacak: %s", e)
            return None

    @staticmethod
    def narrow(rows: list[InventoryRow], birim: str | None = None,
               faaliyet: str | None = None) -> list[InventoryRow]:
        if birim:
            rows = [r for r in rows if r.birim == birim]
        if faaliyet:
            rows = [r for r in rows if r.faaliyet == faaliyet]
        return rows

    @staticmethod
    def templates() -> dict[str, Any]:
        return {"sablonlar": comp_generate.sablon_bilgisi(),
                "faaliyet_bazli": sorted(comp_generate.FAALIYET_BAZLI)}

    @staticmethod
    def faaliyetler(rows: list[InventoryRow]) -> list[dict[str, Any]]:
        sayac: dict[str, int] = {}
        for r in rows:
            if r.faaliyet:
                sayac[r.faaliyet] = sayac.get(r.faaliyet, 0) + 1
        return [{"ad": k, "satir": v} for k, v in sorted(sayac.items(), key=lambda kv: -kv[1])]

    @classmethod
    def preview(cls, req: DocumentRequest, rows: list[InventoryRow]) -> dict[str, Any] | None:
        prof = cls.profile(req, rows)
        bilgi = {s["anahtar"]: s for s in comp_generate.sablon_bilgisi()}
        s = bilgi.get(req.sablon)
        if not s:
            return None
        return {
            "sablon": s["ad"],
            "placeholder": s["placeholder"],
            # kategori/sure/imha ve uretilen bolumler profilden degil envanterden
            # doldugu icin eksik sayilmaz
            "eksik_alanlar": [a for a in prof.eksik_alanlar(s["placeholder"])
                              if a not in comp_generate.TEKRAR_GRUBU
                              and a not in comp_generate.URETILEN_PH
                              and a not in comp_generate.TURETILEN_PH
                              and a not in comp_generate.FAALIYET_PH],
            "uretilen_bolumler": [
                {"alan": a,
                 "kaynak": "yapay_zeka" if a in comp_sections.YAPAY_ZEKA else "veritabani"}
                for a in s.get("uretilen_bolumler", [])],
            "envanter_satiri": len(rows),
            "profil": {
                "isleme_amaci": len(prof.isleme_amaclari),
                "hukuki_sebep": len(prof.hukuki_sebepler),
                "veri_kategorisi": len(prof.veri_kategorileri),
                "kisi_grubu": len(prof.kisi_gruplari),
                "teknik_tedbir": len(prof.teknik_tedbirler),
                "idari_tedbir": len(prof.idari_tedbirler),
            },
        }

    @classmethod
    def generate(cls, req: DocumentRequest, rows: list[InventoryRow]):
        # -> (icerik, kalan_alanlar, dosya_adi, kaynak_haritasi); ValueError/FileNotFoundError yukari
        return comp_generate.uret(req.sablon, cls.profile(req, rows), rows, cls.llm())

    @classmethod
    def generate_all(cls, req: DocumentRequest, rows: list[InventoryRow]) -> tuple[bytes, str, int, list[str]]:
        # Faaliyet basina bir belge uretip ZIP olarak dondurur
        faaliyetler = sorted({r.faaliyet for r in rows if r.faaliyet})
        if not faaliyetler:
            raise ValueError("Envanterde faaliyet bulunamadı")
        buf = io.BytesIO()
        uretilen, hatalar = 0, []
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in faaliyetler:
                alt = [r for r in rows if r.faaliyet == f]
                istek = req.model_copy(update={"faaliyet": f, "faaliyet_filtresi": f})
                try:
                    icerik, _, ad, _k = comp_generate.uret(req.sablon, cls.profile(istek, alt), alt)
                except Exception as e:  # noqa: BLE001 - tek faaliyet patlarsa digerleri uretilsin
                    hatalar.append(f"{f}: {e}")
                    continue
                guvenli = re.sub(r'[\\/:*?"<>|]', "_", f)[:80]
                z.writestr(f"{guvenli}/{ad}", icerik)
                uretilen += 1
            if hatalar:
                z.writestr("HATALAR.txt", "\n".join(hatalar))
        ad = f"{comp_generate.BELGE_ADI[req.sablon].replace(' ', '_')}_tum_faaliyetler.zip"
        return buf.getvalue(), ad, uretilen, hatalar
