"""Kanonik belge ve chunk semasi (plan Faz 1)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Level = Literal["parent", "child"]


def normalize_text(s: str) -> str:
   #Simplify space
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("İ", "i").replace("I", "ı")
    s = s.lower()
    return re.sub(r"\s+", " ", s).strip()


def doc_id_for(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:16]


def chunk_id_for(doc_id: str, parent_ord: int, child_ord: int) -> str:
    raw = f"{doc_id}|{parent_ord}|{child_ord}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class Document:
    #RAW DOCUMENT 
    doc_id: str
    text: str
    belge_adi: str
    kaynak_turu: str
    baglayicilik: str
    otorite_skoru: int
    kategori: str
    url: str
    local_path: str
    karar_no: str | None = None
    karar_tarihi: str | None = None      # ISO: YYYY-MM-DD
    konu_ozeti: str | None = None
    rg_tarihi: str | None = None
    rg_sayisi: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    parent_id: str | None
    level: Level
    text: str              #gomulen/indekslenen metin (metadata oneki dahil)
    text_raw: str          # onek olmadan ham metin
    text_norm: str         # leksik arama icin normalize

    kaynak_turu: str
    baglayicilik: str
    otorite_skoru: int
    belge_adi: str
    url: str
    local_path: str
    kategori: str

    bolum: str | None = None
    madde_no: str | None = None
    madde_basligi: str | None = None
    fikra_no: str | None = None

    karar_no: str | None = None
    karar_tarihi: str | None = None
    konu_ozeti: str | None = None

    madde_atiflari: list[str] = field(default_factory=list)
    kavram_etiketleri: list[str] = field(default_factory=list)

    char_len: int = 0
    token_len: int = 0
    ingest_version: str = "1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_chunk(
    *,
    doc: Document,
    text_raw: str,
    parent_ord: int,
    child_ord: int,
    level: Level,
    parent_id: str | None,
    prefix: str = "",
    **overrides: Any,
) -> Chunk:
    text = f"{prefix}\n{text_raw}".strip() if prefix else text_raw
    data: dict[str, Any] = dict(
        chunk_id=chunk_id_for(doc.doc_id, parent_ord, child_ord),
        doc_id=doc.doc_id,
        parent_id=parent_id,
        level=level,
        text=text,
        text_raw=text_raw,
        text_norm=normalize_text(text_raw),
        kaynak_turu=doc.kaynak_turu,
        baglayicilik=doc.baglayicilik,
        otorite_skoru=doc.otorite_skoru,
        belge_adi=doc.belge_adi,
        url=doc.url,
        local_path=doc.local_path,
        kategori=doc.kategori,
        karar_no=doc.karar_no,
        karar_tarihi=doc.karar_tarihi,
        konu_ozeti=doc.konu_ozeti,
        char_len=len(text),
    )
    data.update(overrides)
    return Chunk(**data)
