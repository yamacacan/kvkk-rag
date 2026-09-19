# Kanonik kurum profili ve sablon placeholder alias haritasi.
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Ayni alan sablonlarda farkli adlarla geciyor; tek profilden hepsi doldurulur.
ALIAS = {
    "kurum": "kurum", "KURUM": "kurum", "organization_name": "kurum",
    "adres": "adres", "organization_address": "adres",
    "web_adres": "web_adres",
    "cagri_merkezi": "cagri_merkezi",
    # faaliyet bazli belgeler (Aydinlatma / Acik Riza): birim ve faaliyetin envanter olgulari
    "BIRIM": "birim", "birim": "birim",
    "ISLEME_AMACI": "isleme_amaci_baslik",
    "kisisel_veriler": "kisisel_veriler", "alici_gruplari": "alici_gruplari", "aktarim_yonu": "aktarim_yonu",
    "FAALİYET": "faaliyet",
    "islenme_amaclari": "isleme_amaclari", "amaclar": "isleme_amaclari",
    "hukuki_sebep": "hukuki_sebepler", "hukuki_sebepler": "hukuki_sebepler",
    "veri_kategorileri": "veri_kategorileri", "kategori": "veri_kategorileri",
    "veri_konusu_kisi": "kisi_gruplari",
    "teknik_tedbirler": "teknik_tedbirler", "tedbirler": "tedbirler",
    "sure": "saklama_suresi", "imha": "imha_yontemi",
    "data_processor_name": "veri_isleyen",
    "contract_title": "sozlesme_adi", "contract_date": "sozlesme_tarihi",
    "protocol_date": "protokol_tarihi",
    "tarih": "belge_tarihi",
}


# Cumle icinde virgulle gecen listeler (madde imi degil): "Kişisel verilerim (Ad Soyad, Özgeçmiş) ..."
SATIR_ICI = {"kisisel_veriler", "alici_gruplari"}


@dataclass
class OrgProfile:
    kurum: str = ""
    adres: str = ""
    web_adres: str = ""
    cagri_merkezi: str = ""
    faaliyet: str = ""
    birim: str = ""
    # Faaliyetin envanter olgulari: kisisel veriler, alici gruplari, aktarim yonu, amac basligi
    kisisel_veriler: list[str] = field(default_factory=list)
    alici_gruplari: list[str] = field(default_factory=list)
    aktarim_yonu: str = ""
    isleme_amaci_baslik: str = ""
    # Envanterden turetilebilen listeler
    isleme_amaclari: list[str] = field(default_factory=list)
    hukuki_sebepler: list[str] = field(default_factory=list)
    veri_kategorileri: list[str] = field(default_factory=list)
    kisi_gruplari: list[str] = field(default_factory=list)
    teknik_tedbirler: list[str] = field(default_factory=list)
    idari_tedbirler: list[str] = field(default_factory=list)
    saklama_suresi: str = ""
    imha_yontemi: str = ""
    # Veri isleyen protokolu icin
    veri_isleyen: str = ""
    sozlesme_adi: str = ""
    sozlesme_tarihi: str = ""
    protokol_tarihi: str = ""
    # Belgenin duzenlenme tarihi (versiyon/onay satirlari); bos birakilirsa uretim gunu
    belge_tarihi: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def tedbirler(self) -> list[str]:
        return self.teknik_tedbirler + self.idari_tedbirler

    def value_for(self, placeholder: str) -> str | None:
        alan = ALIAS.get(placeholder)
        if alan is None:
            return None
        v = self.tedbirler if alan == "tedbirler" else getattr(self, alan, None)
        if v is None:
            return None
        if isinstance(v, list):
            if alan in SATIR_ICI:
                return ", ".join(v)
            return "\n".join(f"• {x}" for x in v) if v else ""
        return str(v)

    def eksik_alanlar(self, placeholders: list[str]) -> list[str]:
        eksik = []
        for ph in placeholders:
            v = self.value_for(ph)
            if v is None or not str(v).strip():
                eksik.append(ph)
        return sorted(set(eksik))


def from_inventory(rows, kurum: str = "", adres: str = "", web_adres: str = "",
                   birim: str | None = None, faaliyet: str | None = None) -> OrgProfile:
    # Profil listelerini gercek envanterden doldurur; sablon uydurma deger icermez.
    def topla(alan: str, n: int = 25) -> list[str]:
        c: dict[str, int] = {}
        for r in rows:
            if birim and (r.birim or "") != birim:
                continue
            if faaliyet and (r.faaliyet or "") != faaliyet:
                continue
            v = getattr(r, alan)
            if v:
                for part in str(v).split("\n"):
                    part = part.strip(" .;")
                    if len(part) > 2:
                        c[part] = c.get(part, 0) + 1
        return [k for k, _ in sorted(c.items(), key=lambda kv: -kv[1])[:n]]

    secili = [r for r in rows if (not birim or (r.birim or "") == birim) and (not faaliyet or (r.faaliyet or "") == faaliyet)]
    # birim adi kisa olabilir ("İK"): topla()'nin uzunluk filtresine takilmasin
    birim_sayac: dict[str, int] = {}
    for r in secili:
        b = (r.birim or "").strip()
        if b:
            birim_sayac[b] = birim_sayac.get(b, 0) + 1
    birimler = [max(birim_sayac, key=birim_sayac.get)] if birim_sayac else []
    yurt_disi = any((r.yurt_disi_aktarim or "").strip().lower() in ("evet", "var", "true", "1") for r in secili)
    amaclar = topla("isleme_amaci", 3)
    return OrgProfile(
        kurum=kurum, adres=adres, web_adres=web_adres, faaliyet=faaliyet or "",
        birim=birim or (birimler[0] if birimler else ""),
        kisisel_veriler=topla("kisisel_veri", 30),
        alici_gruplari=topla("alici_grubu", 10) or ["yetkili kurum ve kuruluşlar"],
        aktarim_yonu="yurt dışına ve yurt içine" if yurt_disi else "yurt içine",
        isleme_amaci_baslik=" / ".join(amaclar) if amaclar else (faaliyet or ""),
        isleme_amaclari=topla("isleme_amaci"),
        hukuki_sebepler=topla("hukuki_sebep"),
        veri_kategorileri=topla("veri_kategorisi"),
        kisi_gruplari=topla("kisi_grubu"),
        teknik_tedbirler=topla("teknik_tedbir"),
        idari_tedbirler=topla("idari_tedbir"),
        saklama_suresi=(topla("saklama_suresi", 1) or [""])[0],
    )
