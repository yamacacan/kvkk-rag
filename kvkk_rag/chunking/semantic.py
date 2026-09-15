"""Serbest metinli kararlar icin semantik chunking.

Yontem (plan Faz 1.4):
  1. Paragraflar (detail.txt'te her satir bir paragraf) sirayla ~TARGET karaktere
     kadar birlestirilir.
  2. Ardisik birimlerin BERTurk-STS kosinus benzerligi hesaplanir; benzerligin
     5. persentilin altina dustugu yerde konu degismis sayilir ve kesilir.
  3. HARD_MAX asilirsa zorla bolunur (embedding 512 token siniri icin).

parent = kararin tamami, child = semantik blok.
"""
from __future__ import annotations

import numpy as np

from ..config import settings
from ..index import embedder
from ..ingest.models import Chunk, Document, make_chunk

TARGET_CHARS = 700
# 1300 + ~120 karakterlik metadata oneki ~ 470 token; BERTurk-STS 512 sinirinin altinda kalir.
HARD_MAX_CHARS = 1300
BREAK_PERCENTILE = 5


def _merge_paragraphs(paragraphs: list[str]) -> list[str]:
    """Kisa paragraflari ~TARGET_CHARS'a kadar birlestirir."""
    units: list[str] = []
    buf = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if not buf:
            buf = p
        elif len(buf) + len(p) + 1 <= TARGET_CHARS:
            buf = f"{buf}\n{p}"
        else:
            units.append(buf)
            buf = p
    if buf:
        units.append(buf)
    return units


def _hard_slice(text: str) -> list[str]:
    # Cumle siniri yoksa (uzun listeler, madde isaretsiz bloklar) kelime sinirinda kes
    out, cur = [], ""
    for word in text.split(" "):
        if len(cur) + len(word) + 1 > HARD_MAX_CHARS and cur:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        out.append(cur)
    return out


def _split_oversized(text: str) -> list[str]:
    # HARD_MAX_CHARS'i asan parcayi once cumle, gerekirse kelime sinirinda boler.
    # Kelime geri dusumu sart: tek cumleli uzun bloklar aksi halde 512 token
    # sinirinda sessizce kirpilir.
    if len(text) <= HARD_MAX_CHARS:
        return [text]

    out, cur = [], ""
    for sent in text.replace("\n", " ").split(". "):
        cand = f"{cur}. {sent}".strip(". ") if cur else sent
        if len(cand) > HARD_MAX_CHARS and cur:
            out.append(cur.strip() + ".")
            cur = sent
        else:
            cur = cand
    if cur:
        out.append(cur.strip())

    return [piece for part in out for piece in
            ([part] if len(part) <= HARD_MAX_CHARS else _hard_slice(part))]


def semantic_blocks(paragraphs: list[str]) -> list[str]:
    units = _merge_paragraphs(paragraphs)
    if len(units) <= 1:
        return [b for u in units for b in _split_oversized(u)]

    vecs = embedder.embed(units)
    sims = np.sum(vecs[:-1] * vecs[1:], axis=1)  # normalize edilmis -> kosinus
    threshold = float(np.percentile(sims, BREAK_PERCENTILE))

    blocks, cur = [], units[0]
    for i, u in enumerate(units[1:]):
        too_long = len(cur) + len(u) + 1 > HARD_MAX_CHARS
        topic_shift = sims[i] < threshold
        if topic_shift or too_long:
            blocks.append(cur)
            cur = u
        else:
            cur = f"{cur}\n{u}"
    blocks.append(cur)

    return [b for blk in blocks for b in _split_oversized(blk)]


def chunk_karar(doc: Document, paragraphs: list[str], parent_ord: int = 0) -> list[Chunk]:
    """parent = kararin tamami, child = semantik bloklar."""
    if not paragraphs:
        return []

    bits = [doc.kaynak_turu.replace("_", " ").title()]
    if doc.karar_no:
        bits.append(doc.karar_no)
    if doc.karar_tarihi:
        bits.append(doc.karar_tarihi)
    if doc.konu_ozeti:
        bits.append(doc.konu_ozeti[:120])
    prefix = "[" + " · ".join(bits) + "]"

    full = "\n".join(paragraphs)
    parent = make_chunk(
        doc=doc, text_raw=full, parent_ord=parent_ord, child_ord=0,
        level="parent", parent_id=None, prefix=prefix,
    )
    chunks = [parent]
    for i, block in enumerate(semantic_blocks(paragraphs), start=1):
        chunks.append(make_chunk(
            doc=doc, text_raw=block, parent_ord=parent_ord, child_ord=i,
            level="child", parent_id=parent.chunk_id, prefix=prefix,
        ))
    return chunks
