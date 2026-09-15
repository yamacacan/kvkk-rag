"""PDF metin katmani cikarimi. Taranmis (metinsiz) PDF'leri tespit edip isaretler."""
from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

MIN_WORDS_PER_PAGE = 20  # bunun altindaki PDF taranmis goruntu sayilir


def load(path: Path) -> dict:
    reader = PdfReader(str(path))
    pages = [(pg.extract_text() or "") for pg in reader.pages]
    text = "\n".join(pages)
    words = len(text.split())
    n_pages = max(len(pages), 1)

    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(ln.strip() for ln in text.splitlines()).strip()

    return {
        "text": text,
        "n_pages": n_pages,
        "n_words": words,
        "is_scanned": words / n_pages < MIN_WORDS_PER_PAGE,
    }
