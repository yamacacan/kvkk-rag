"""Chunk zenginlestirme: metinden madde atiflarini ve kavram etiketlerini cikarir.

Turkce mevzuat atiflari cok bicimli:
    "6698 sayılı Kanunun 12 nci maddesi"
    "Kanunun 5 inci maddesinin ikinci fıkrasının (ç) bendi"
    "11 inci maddesinin birinci fıkrasının (a) bendi"
    "Kanun'un 6. maddesi"
Normalize bicim: "6698/12", "6698/5/2-ç"
"""
from __future__ import annotations

import re

from ..ingest.models import Chunk

ORD = r"(?:inci|ıncı|nci|ncı|üncü|uncu|ncü|uncü)"

# "<no> (inci) madde(sinin)"  -> madde numarasi
MADDE_REF = re.compile(rf"(\d+)\s*(?:\.|{ORD})?\s*madde", re.IGNORECASE)

# fikra: "ikinci fıkrasının" | "(1) numaralı fıkra" | "2 nci fıkra"
FIKRA_WORD = {
    "birinci": "1", "ikinci": "2", "üçüncü": "3", "dördüncü": "4", "beşinci": "5",
    "altıncı": "6", "yedinci": "7", "sekizinci": "8", "dokuzuncu": "9", "onuncu": "10",
}
FIKRA_REF = re.compile(
    rf"(?:\((\d+)\)\s*numaralı\s*fıkra|({'|'.join(FIKRA_WORD)})\s*fıkra|(\d+)\s*(?:\.|{ORD})\s*fıkra)",
    re.IGNORECASE,
)
BENT_REF = re.compile(r"\(([a-zçğıöşü])\)\s*bend", re.IGNORECASE)

# Hangi kanuna atif: yakinda "6698" gecmiyorsa varsayilan 6698 (korpus KVKK odakli).
# "19816 sayılı Resmî Gazete" bir kanun degil - RG sayilari dislanir.
KANUN_NO = re.compile(r"(\d{3,5})\s*sayılı(?!\s*Resm)")

# Kavram etiketleri: sorgu-genisletme ve graf icin kaba sinyal
KAVRAMLAR = {
    "biyometrik_veri": ["biyometrik", "parmak izi", "yüz tanıma", "retina", "avuç içi"],
    "ozel_nitelikli_veri": ["özel nitelikli", "sağlık verisi", "din", "irk", "etnik", "sendika", "ceza mahkûmiyeti"],
    "acik_riza": ["açık rıza", "rızası olmaksızın", "rıza alınmaksızın"],
    "aydinlatma": ["aydınlatma yükümlülüğü", "aydınlatma metni", "bilgilendirme yükümlülüğü"],
    "veri_guvenligi": ["veri güvenliği", "teknik ve idari tedbir", "güvenlik ihlali", "veri ihlali"],
    "yurt_disi_aktarim": ["yurt dışına aktar", "yurtdışına aktar", "standart sözleşme", "bağlayıcı şirket kural"],
    "imha": ["silinmesi", "yok edilmesi", "anonim hale getirilmesi", "periyodik imha", "saklama süresi"],
    "verbis": ["veri sorumluları sicili", "verbis", "sicile kayıt"],
    "ilgili_kisi_basvuru": ["ilgili kişinin başvuru", "başvuru hakkı", "şikâyet hakkı", "şikayet hakkı"],
    "cerez": ["çerez", "cookie"],
}


def extract_madde_atiflari(text: str, default_kanun: str = "6698") -> list[str]:
    refs: list[str] = []
    for m in MADDE_REF.finditer(text):
        madde = m.group(1)
        # Atiftan onceki pencerede EN YAKIN "<no> sayılı" ifadesi baglayicidir;
        # dar pencere "657 sayılı Kanunun ... 109 uncu maddesi"ni kacirir.
        window = text[max(0, m.start() - 160): m.start()]
        kanun_hits = KANUN_NO.findall(window)
        kanun = kanun_hits[-1] if kanun_hits else default_kanun

        tail = text[m.end(): m.end() + 120]
        fikra = None
        fm = FIKRA_REF.search(tail)
        if fm:
            fikra = fm.group(1) or FIKRA_WORD.get((fm.group(2) or "").lower()) or fm.group(3)
        bent = None
        bm = BENT_REF.search(tail)
        if bm:
            bent = bm.group(1).lower()

        ref = f"{kanun}/{madde}"
        if fikra:
            ref += f"/{fikra}"
            if bent:
                ref += f"-{bent}"
        refs.append(ref)

    return sorted(set(refs))


def extract_kavramlar(text: str) -> list[str]:
    low = text.lower()
    return sorted(k for k, terms in KAVRAMLAR.items() if any(t in low for t in terms))


def enrich(chunk: Chunk) -> Chunk:
    chunk.madde_atiflari = extract_madde_atiflari(chunk.text_raw)
    chunk.kavram_etiketleri = extract_kavramlar(chunk.text_raw)
    return chunk
