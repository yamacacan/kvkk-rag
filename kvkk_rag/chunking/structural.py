"""Mevzuat icin yapisal chunking: parent = MADDE, child = fikra.

Turk mevzuat metninde madde basligi MADDE isaretinden ONCEKI satirda durur:

    BİRİNCİ BÖLÜM
    Amaç, Kapsam ve Tanımlar
    Amaç                      <- madde basligi
    MADDE 1- (1) Bu Kanunun amacı, ...
                (2) ...

Iki tire stili birden desteklenir: "MADDE 1 – " (U+2013, 2018 RG) ve
"MADDE 1- " (ASCII, 2022+ RG ve Kanun PDF'i).
"""
from __future__ import annotations

import re

from ..ingest.models import Chunk, Document, make_chunk

MADDE_RE = re.compile(
    r"^[ \t]*(?:(GEÇİCİ|EK)[ \t]+)?MADDE[ \t]*(\d+)[ \t]*[-–—][ \t]*",
    re.MULTILINE,
)
FIKRA_RE = re.compile(r"(?m)^[ \t]*\((\d+)\)[ \t]*")
BOLUM_RE = re.compile(
    r"^[ \t]*((?:BİRİNCİ|İKİNCİ|ÜÇÜNCÜ|DÖRDÜNCÜ|BEŞİNCİ|ALTINCI|YEDİNCİ|SEKİZİNCİ|DOKUZUNCU|ONUNCU)[ \t]+BÖLÜM)[ \t]*$",
    re.MULTILINE,
)
# Madde basligi: MADDE satirindan onceki, cumle olmayan kisa satir
HEADING_MAX_LEN = 120


def _find_bolum(text: str, pos: int) -> str | None:
    """pos'tan onceki en yakin BOLUM basligini (varsa alt basligiyla) dondurur."""
    last = None
    for m in BOLUM_RE.finditer(text, 0, pos):
        last = m
    if not last:
        return None
    tail = text[last.end():pos].lstrip("\n")
    alt = tail.split("\n", 1)[0].strip() if tail else ""
    return f"{last.group(1)} - {alt}".strip(" -") if alt and len(alt) < HEADING_MAX_LEN else last.group(1)


TR_LOWER = set("abcçdefgğhıijklmnoöprsştuüvyz")
CONJ_END = re.compile(r"\b(ve|veya|ile|ya)\s*$", re.IGNORECASE)


def _is_heading_line(line: str) -> bool:
    if not line or len(line) > HEADING_MAX_LEN:
        return False
    if line.endswith((".", ":", ";", "?")):
        return False
    return not BOLUM_RE.match(line)


def _find_heading(text: str, madde_start: int) -> tuple[str, int] | None:
    """MADDE isaretinden onceki baslik. Kaynakta satira bolunmus olabilir
    ('Amaç ve' / 'kapsam'); yalnizca gercek bir devam isareti varsa birlestirir.

    Donus: (baslik_metni, metindeki_baslangic_ofseti)
    """
    before = text[:madde_start]
    stripped = before.rstrip()
    if not stripped:
        return None

    lines = stripped.split("\n")
    last = lines[-1].strip()
    if not _is_heading_line(last):
        return None

    parts = [last]
    start_idx = len(lines) - 1
    # Geriye dogru yalnizca sarma (wrap) isareti varken birlestir:
    # ya mevcut parca kucuk harfle basliyor ya da onceki satir baglacla bitiyor.
    while start_idx > 0:
        prev = lines[start_idx - 1].strip()
        if not prev or not _is_heading_line(prev):
            break
        wraps = parts[0][:1] in TR_LOWER or CONJ_END.search(prev) is not None
        if not wraps:
            break
        if len(" ".join([prev] + parts)) > HEADING_MAX_LEN:
            break
        parts.insert(0, prev)
        start_idx -= 1

    heading = " ".join(parts)
    offset = len(stripped) - len("\n".join(lines[start_idx:]))
    return heading, offset


def split_fikralar(body: str) -> list[tuple[str | None, str]]:
    """Madde govdesini (fikra_no, metin) listesine ayirir. Fikra yoksa tek parca."""
    marks = list(FIKRA_RE.finditer(body))
    if not marks:
        return [(None, body.strip())]

    out: list[tuple[str | None, str]] = []
    # Ilk fikradan onceki giris metni (nadiren olur) atilmaz, ilk fikraya eklenir
    preamble = body[: marks[0].start()].strip()
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        seg = body[m.end(): end].strip()
        if i == 0 and preamble:
            seg = f"{preamble}\n{seg}".strip()
        if seg:
            out.append((m.group(1), seg))
    return out or [(None, body.strip())]


def chunk_mevzuat(doc: Document) -> list[Chunk]:
    """Mevzuat metnini madde (parent) ve fikra (child) chunk'larina ayirir."""
    text = doc.text
    matches = list(MADDE_RE.finditer(text))
    if not matches:
        return []

    chunks: list[Chunk] = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        # Sonraki maddenin basligi bu maddenin govdesine karismasin
        body_end = end
        if idx + 1 < len(matches):
            nxt = _find_heading(text, end)
            if nxt:
                body_end = nxt[1]

        prefix_kind = m.group(1)  # GEÇİCİ / EK / None
        no = m.group(2)
        madde_no = f"{prefix_kind} {no}".strip() if prefix_kind else no
        head = _find_heading(text, m.start())
        basligi = head[0] if head else None
        bolum = _find_bolum(text, m.start())
        body = text[m.end(): body_end].strip()
        if not body:
            continue

        madde_tam = f"MADDE {madde_no}" + (f" - {basligi}" if basligi else "")
        parent_prefix = f"[{doc.belge_adi} · {madde_tam}]"

        parent = make_chunk(
            doc=doc, text_raw=body, parent_ord=idx, child_ord=0,
            level="parent", parent_id=None, prefix=parent_prefix,
            bolum=bolum, madde_no=madde_no, madde_basligi=basligi,
        )
        chunks.append(parent)

        for c_ord, (fikra_no, seg) in enumerate(split_fikralar(body), start=1):
            label = f"{madde_tam}/{fikra_no}" if fikra_no else madde_tam
            chunks.append(make_chunk(
                doc=doc, text_raw=seg, parent_ord=idx, child_ord=c_ord,
                level="child", parent_id=parent.chunk_id,
                prefix=f"[{doc.belge_adi} · {label}]",
                bolum=bolum, madde_no=madde_no, madde_basligi=basligi,
                fikra_no=fikra_no,
            ))
    return chunks
