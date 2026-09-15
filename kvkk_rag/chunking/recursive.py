# Sabit uzunluk / recursive chunking taban cizgisi (LangChain varsayilani, XTraReg konfigu).
# Literaturdeki karsilastirmalarda "Simple/Recursive" kolu budur.
from __future__ import annotations

from ..ingest.models import Chunk, Document, make_chunk

CHUNK_SIZE = 1000
OVERLAP = 200
SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split(text: str, size: int, seps: list[str]) -> list[str]:
    if len(text) <= size:
        return [text] if text.strip() else []
    if not seps:
        return [text[i:i + size] for i in range(0, len(text), size)]

    sep, rest = seps[0], seps[1:]
    parts, buf = [], ""
    for piece in text.split(sep):
        cand = f"{buf}{sep}{piece}" if buf else piece
        if len(cand) > size and buf:
            parts.append(buf)
            buf = piece
        else:
            buf = cand
    if buf:
        parts.append(buf)

    out = []
    for p in parts:
        out.extend(_split(p, size, rest) if len(p) > size else ([p] if p.strip() else []))
    return out


def _with_overlap(parts: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(parts) < 2:
        return parts
    out = [parts[0]]
    for prev, cur in zip(parts, parts[1:]):
        out.append((prev[-overlap:] + " " + cur).strip())
    return out


def chunk_recursive(doc: Document, parent_ord: int = 0,
                    size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[Chunk]:
    pieces = _with_overlap(_split(doc.text, size, SEPARATORS), overlap)
    if not pieces:
        return []

    parent = make_chunk(doc=doc, text_raw=doc.text, parent_ord=parent_ord, child_ord=0,
                        level="parent", parent_id=None)
    chunks = [parent]
    for i, piece in enumerate(pieces, start=1):
        chunks.append(make_chunk(doc=doc, text_raw=piece, parent_ord=parent_ord,
                                 child_ord=i, level="child", parent_id=parent.chunk_id))
    return chunks
