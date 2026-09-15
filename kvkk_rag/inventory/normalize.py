# Envanterdeki ham degerleri kanonik taksonomiye esler. Tahmin etmez, guven skoru dondurur.
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from . import taxonomy

TR_MAP = str.maketrans("İIŞĞÜÖÇ", "iışğüöç")
PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

# Envanterde gorulmus yazim hatalari. Duzeltme degil, eslemede tolerans saglar.
TYPO = {
    "temek": "temel",       # "TEMEK HAK VE ÖZGÜRLÜKLER"
    "doğudan": "doğrudan",  # "DOĞUDAN DOĞRUYA"
    "dogudan": "dogrudan",
}

EXACT = "birebir"
NORMALIZED = "normalize"
PREFIX = "onek"
FUZZY = "bulanik"
CUSTOM = "serbest_metin"
UNMATCHED = "eslesmedi"


@dataclass
class Match:
    ham: str
    kanonik: str | None
    yontem: str
    guven: float

    @property
    def kesin(self) -> bool:
        return self.yontem in (EXACT, NORMALIZED)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).translate(TR_MAP).lower()
    s = PUNCT.sub(" ", s)
    tokens = [TYPO.get(t, t) for t in s.split()]
    return " ".join(tokens)


def _tokens(s: str) -> set[str]:
    # Tek harfli baglaclar ayirt edici degil
    return {t for t in fold(s).split() if len(t) > 2}


def match_one(raw: str, canon: list[str], fuzzy_threshold: float = 0.72) -> Match:
    raw = (raw or "").strip()
    if not raw:
        return Match(raw, None, UNMATCHED, 0.0)

    if raw.lower().startswith(taxonomy.DIGER_PREFIX):
        if raw.endswith(")"):
            icerik = raw[len(taxonomy.DIGER_PREFIX):-1].strip()
            by_fold = {fold(c): c for c in canon}
            if fold(icerik) in by_fold:
                return Match(raw, by_fold[fold(icerik)], NORMALIZED, 0.99)
        return Match(raw, raw, CUSTOM, 1.0)

    if raw in canon:
        return Match(raw, raw, EXACT, 1.0)

    folded = fold(raw)
    by_fold = {fold(c): c for c in canon}
    if folded in by_fold:
        return Match(raw, by_fold[folded], NORMALIZED, 0.98)

    # Kisaltilmis/kirpilmis degerler: biri digerinin oneki
    for cf, c in by_fold.items():
        if cf.startswith(folded) or folded.startswith(cf):
            kisa, uzun = sorted((len(folded), len(cf)))
            return Match(raw, c, PREFIX, round(0.80 + 0.15 * kisa / uzun, 3))

    # Jaccard token ortusmesi
    rt = _tokens(raw)
    if rt:
        best, best_score = None, 0.0
        for c in canon:
            ct = _tokens(c)
            if not ct:
                continue
            score = len(rt & ct) / len(rt | ct)
            if score > best_score:
                best, best_score = c, score
        if best and best_score >= fuzzy_threshold:
            return Match(raw, best, FUZZY, round(best_score, 3))

    return Match(raw, None, UNMATCHED, 0.0)


# Bir hucrede birden cok deger olabiliyor (satir sonu, noktali virgul veya
# "...maktadir." ile biten cumlelerin arka arkaya yazilmasi)
SPLIT = re.compile(r"[\n;]+|(?<=\.)\s{2,}")


def split_values(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip(" .;\t") for p in SPLIT.split(raw)]
    return [p for p in parts if len(p) > 2]


def match_multi(raw: str, kind: str) -> list[Match]:
    canon = taxonomy.values(kind)
    parts = split_values(raw)
    if len(parts) <= 1:
        return [match_one(raw, canon)]
    return [match_one(p, canon) for p in parts]


def match_column(values: list[str], kind: str) -> dict[str, Match]:
    # Benzersiz degerler uzerinde calisir; 3108 satirda 12 benzersiz deger var
    canon = taxonomy.values(kind)
    out: dict[str, Match] = {}
    for v in sorted(set(v for v in values if v)):
        for part in (split_values(v) or [v]):
            if part not in out:
                out[part] = match_one(part, canon)
    return out


def report(matches: dict[str, Match]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in matches.values():
        out[m.yontem] = out.get(m.yontem, 0) + 1
    return out
