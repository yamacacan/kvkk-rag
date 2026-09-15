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


def madde_for_sebep(sebep_adi: str) -> str | None:
    for it in load().get("hukuki_sebep", []):
        if it["ad"] == sebep_adi:
            return SEBEP_GRUBU_MADDE.get(it["aciklama"])
    return None


def is_ozel_nitelikli_sebep(sebep_adi: str) -> bool:
    return madde_for_sebep(sebep_adi) == "6"


def is_ozel_nitelikli_kategori(kategori: str) -> bool:
    return kategori.strip() in OZEL_NITELIKLI_KATEGORILER
