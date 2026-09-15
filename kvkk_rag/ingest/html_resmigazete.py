"""Resmi Gazete HTML'lerini temiz metne cevirir.

Bu dosyalar MS Word export'u: Windows-1254 kodlu, iki buyuk <style> blogu ve
govde basinda Word dokuman-ozellikleri copu ("Normal dizgi1 ... MicrosoftInternetExplorer4
false TR X-NONE") iceriyor. <script>/<nav> yok.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

# Word export artigi: "Resmi Gazete Sayi :" satirindan ONCESI atilir
RG_HEADER_RE = re.compile(r"Resm.?\s*Gazete\s*Say.?\s*:\s*(\d+)", re.IGNORECASE)
RG_DATE_RE = re.compile(
    r"(\d{1,2})\s+(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(\d{4})"
)
AY = {"Ocak": "01", "Şubat": "02", "Mart": "03", "Nisan": "04", "Mayıs": "05", "Haziran": "06",
      "Temmuz": "07", "Ağustos": "08", "Eylül": "09", "Ekim": "10", "Kasım": "11", "Aralık": "12"}


def decode_bytes(raw: bytes) -> str:
    for enc in ("cp1254", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def html_to_text(raw: bytes) -> str:
    soup = BeautifulSoup(decode_bytes(raw), "html.parser")
    for tag in soup(["script", "style", "xml"]):
        tag.decompose()
    # Word namespace artiklari (o:p, w:*, v:*)
    for tag in soup.find_all(lambda t: t.name and ":" in t.name):
        tag.unwrap()

    text = soup.get_text("\n")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(ln.strip() for ln in text.splitlines()).strip()


def extract_rg_meta(text: str) -> tuple[str | None, str | None]:
    """(rg_tarihi_iso, rg_sayisi) dondurur."""
    sayi = None
    m = RG_HEADER_RE.search(text)
    if m:
        sayi = m.group(1)
    tarih = None
    d = RG_DATE_RE.search(text)
    if d:
        gun, ay, yil = d.groups()
        tarih = f"{yil}-{AY[ay]}-{int(gun):02d}"
    return tarih, sayi


def strip_preamble(text: str) -> str:
    """Word copunu ve RG baslik blogunu atip asil mevzuat metnini dondurur."""
    m = RG_HEADER_RE.search(text)
    if m:
        text = text[m.end():]
    # Ilk anlamli baslik: "YONETMELIK" / "TEBLIG" sonrasi
    m2 = re.search(r"^(YÖNETMELİK|TEBLİĞ|KANUN)\s*$", text, re.MULTILINE)
    if m2:
        text = text[m2.end():]
    return text.strip()


def load(path: Path) -> dict:
    raw = path.read_bytes()
    full = html_to_text(raw)
    rg_tarihi, rg_sayisi = extract_rg_meta(full)
    return {
        "text": strip_preamble(full),
        "rg_tarihi": rg_tarihi,
        "rg_sayisi": rg_sayisi,
    }
