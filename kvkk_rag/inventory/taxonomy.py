# KVKK kanonik taksonomileri ve mevzuat madde eslemesi.
from __future__ import annotations

import functools
import json
from typing import Any

from ..config import settings

TAXONOMY_PATH = settings.DATA_DIR / "inventory" / "taksonomi.json"

# Seeder'daki 'description' alani hukuki sebebi KVKK maddesine baglar.
# Deterministik eslemedir; LLM'e birakilmaz.
SEBEP_GRUBU_MADDE = {
    "Kişisel Veri İşleme Şartları": "5",
    "Özel Nitelikli Kişisel Veri İşleme Şartları": "6",
    "İstisna Sebepler ile Veri İşleme": "28",
}

# VERBIS veri kategorilerinden ozel nitelikli olanlar (KVKK m.6/1)
OZEL_NITELIKLI_KATEGORILER = {
    "Sağlık Bilgileri", "Ceza Mahkumiyeti ve Güvenlik Tedbirleri", "Sendika Üyeliği",
    "Biyometrik Veri", "Genetik Veri", "Din, Mezhep ve Felsefi İnanç",
    "Irk ve Etnik Köken", "Siyasi Düşünce", "Felsefi İnanç, Din, Mezhep ve Diğer İnançlar",
    "Kılık ve Kıyafet", "Dernek Üyeliği", "Vakıf Üyeliği", "Cinsel Hayat",
}

# Envanterdeki serbest metin kalibi: "Diğer(...)"
DIGER_PREFIX = "diğer("


@functools.lru_cache(maxsize=1)
def load() -> dict[str, list[dict[str, Any]]]:
    if not TAXONOMY_PATH.exists():
        raise FileNotFoundError(
            f"{TAXONOMY_PATH} yok. Once: python scripts/parse_taxonomy.py")
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def values(kind: str) -> list[str]:
    return [it["ad"] for it in load().get(kind, [])]


SEBEP_GRUBU_BASLIK = {
    "5": "Kişisel veri işleme şartları",
    "6": "Özel nitelikli kişisel veri işleme şartları",
    "28": "İstisna sebepler",
}


def kanonik_sebep(sebep_adi: str) -> str | None:
    # Ham degeri kanonik ada esler: birebir, normalize, kirpilmis onek ("...") veya bulanik.
    ad = (sebep_adi or "").strip()
    if not ad:
        return None
    adlar = values("hukuki_sebep")
    if ad in adlar:
        return ad
    from . import normalize  # dongusel import: normalize -> taxonomy
    m = normalize.match_one(ad, adlar)
    return m.kanonik if m.yontem in (normalize.EXACT, normalize.NORMALIZED, normalize.PREFIX, normalize.FUZZY) else None


def maddeler_for_sebep(sebep_adi: str) -> set[str]:
    # Ayni ad birden fazla grupta olabilir ("Kanunlarda Açıkça Öngörülmesi" hem m.5 hem m.6);
    # bu yuzden tek madde degil, adin gectigi tum maddeler doner.
    ad = kanonik_sebep(sebep_adi)
    return {SEBEP_GRUBU_MADDE[it["aciklama"]] for it in load().get("hukuki_sebep", [])
            if it["ad"] == ad and it["aciklama"] in SEBEP_GRUBU_MADDE}


def madde_for_sebep(sebep_adi: str) -> str | None:
    # Geriye donuk: tek madde; belirsiz adda m.6 (dar sart) yerine genel sart (m.5) doner
    maddeler = maddeler_for_sebep(sebep_adi)
    for m in ("5", "6", "28"):
        if m in maddeler:
            return m
    return None


def is_ozel_nitelikli_sebep(sebep_adi: str) -> bool:
    return "6" in maddeler_for_sebep(sebep_adi)


def hukuki_sebep_detay() -> list[dict[str, Any]]:
    # Acilir liste icin: madde grubuna gore, ad tekrarlari korunarak (m.5/m.6 ayni ad)
    return [{"ad": it["ad"], "madde": SEBEP_GRUBU_MADDE.get(it["aciklama"]),
             "grup": SEBEP_GRUBU_BASLIK.get(SEBEP_GRUBU_MADDE.get(it["aciklama"]), it["aciklama"])}
            for it in load().get("hukuki_sebep", [])]


def is_ozel_nitelikli_kategori(kategori: str) -> bool:
    return kategori.strip() in OZEL_NITELIKLI_KATEGORILER
