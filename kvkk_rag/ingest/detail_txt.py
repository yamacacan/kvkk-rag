"""kvkk.gov.tr detay sayfalarindan uretilen .detail.txt dosyalarini okur.

Sabit yapi (scrape_kvkk.py ciktisi):
    L0: baslik
    L1: (bos)
    L2: baslik tekrari (bazen kisaltilmis)
    L3: Karar Tarihi
    L4: : 21/12/2017          <- bosluklu ya da bosluksuz
    L5: Karar No
    L6: : 2017/61
    L7: Konu Ozeti
    L8: : ...
    L9+: govde (her paragraf tek satir)

Karar No / Tarihi 346 dosyanin 116'sinda YOK; bu durumda baslik regex'i denenir.
"""
from __future__ import annotations

import re
from pathlib import Path

META_LABELS = {"Karar Tarihi", "Karar No", "Konu Özeti", "Veri Sorumlusu"}

# "10/06/2025 Tarihli ve 2025/1072 sayılı" kalibindan tarih+no cikarimi
TITLE_META_RE = re.compile(
    r"(\d{2}[./]\d{2}[./]\d{4})\s*[Tt]arih\w*\s*ve\s*(\d{4}[/-]\d+)"
)
DATE_RE = re.compile(r"^(\d{2})[./](\d{2})[./](\d{4})$")

# Rehber sayfalarinda govdeye karisan bagli link artiklari
LINK_NOISE = re.compile(r"^(tıklayınız|tıklayınız\.|Devamını Gör)$", re.IGNORECASE)


def to_iso(date_str: str | None) -> str | None:
    if not date_str:
        return None
    m = DATE_RE.match(date_str.strip())
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{mo}-{d}"


def parse_detail_txt(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return {"baslik": "", "meta": {}, "govde": ""}

    baslik = lines[0].strip()
    meta: dict[str, str] = {}

    i = 1
    # L2 baslik tekrarini atla (birebir ya da baslik'in on eki olan varyant)
    while i < len(lines):
        cur = lines[i].strip()
        if not cur:
            i += 1
            continue
        if cur == baslik or (len(cur) > 20 and baslik.startswith(cur[:40])):
            i += 1
            continue
        break

    # Iki satirli metadata blogu: etiket / :deger
    while i < len(lines) - 1:
        label = lines[i].strip()
        if label not in META_LABELS:
            break
        value = lines[i + 1].strip()
        if value.startswith(":"):
            meta[label] = value[1:].strip()
            i += 2
        else:
            i += 1

    govde_lines = [
        ln.strip() for ln in lines[i:]
        if ln.strip() and not LINK_NOISE.match(ln.strip())
    ]

    karar_no = meta.get("Karar No")
    karar_tarihi = meta.get("Karar Tarihi")
    if not (karar_no and karar_tarihi):
        m = TITLE_META_RE.search(baslik)
        if m:
            karar_tarihi = karar_tarihi or m.group(1)
            karar_no = karar_no or m.group(2).replace("-", "/")

    return {
        "baslik": baslik,
        "karar_no": karar_no,
        "karar_tarihi": to_iso(karar_tarihi),
        "konu_ozeti": meta.get("Konu Özeti"),
        "veri_sorumlusu": meta.get("Veri Sorumlusu"),
        "govde": "\n".join(govde_lines),
        "paragraflar": govde_lines,
    }
