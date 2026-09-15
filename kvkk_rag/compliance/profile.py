# Kanonik kurum profili ve sablon placeholder alias haritasi.
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Ayni alan sablonlarda farkli adlarla geciyor; tek profilden hepsi doldurulur.
ALIAS = {
    "kurum": "kurum", "KURUM": "kurum", "organization_name": "kurum",
    "adres": "adres", "organization_address": "adres",
    "web_adres": "web_adres",
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
}


@dataclass
class OrgProfile:
    kurum: str = ""
    adres: str = ""
    web_adres: str = ""
    faaliyet: str = ""
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

    return OrgProfile(
        kurum=kurum, adres=adres, web_adres=web_adres, faaliyet=faaliyet or "",
        isleme_amaclari=topla("isleme_amaci"),
        hukuki_sebepler=topla("hukuki_sebep"),
        veri_kategorileri=topla("veri_kategorisi"),
        kisi_gruplari=topla("kisi_grubu"),
        teknik_tedbirler=topla("teknik_tedbir"),
        idari_tedbirler=topla("idari_tedbir"),
        saklama_suresi=(topla("saklama_suresi", 1) or [""])[0],
    )
