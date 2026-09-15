"""Ingest orkestratoru: manifest -> Document -> Chunk.

Yonlendirme kurallari:
  * Mevzuat (kanun/yonetmelik/teblig)  -> yapisal chunking (madde/fikra)
  * Kararlar, rehberler                -> semantik chunking
  * Metinsiz (taranmis) PDF, MADDE bulunamayan mevzuat -> atlanir, gerekcesi loglanir
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator

from ..config import settings
from ..chunking.enrich import enrich
from ..chunking.semantic import chunk_karar
from ..chunking.structural import MADDE_RE, chunk_mevzuat
from . import detail_txt, html_resmigazete, pdf_text
from .models import Chunk, Document, doc_id_for

STRUCTURAL_SOURCES = {"kanun", "yonetmelik", "teblig"}


def _resolve(local_path: str) -> Path:
    """manifest'teki repo-goreli yolu calisilan dizine gore cozer."""
    p = Path(local_path)
    if p.exists():
        return p
    # 'data/...' onekini settings.DATA_DIR'e tasi (konteynerde /app/data)
    parts = p.parts
    if parts and parts[0] == "data":
        return settings.DATA_DIR.joinpath(*parts[1:])
    return p


def _prefer_text_twin(path: Path) -> Path:
    """.detail.html yerine yaninda duran temiz .detail.txt varsa onu kullan."""
    if path.name.endswith(".detail.html"):
        twin = path.with_name(path.name[: -len(".html")] + ".txt")
        if twin.exists():
            return twin
    return path


def load_document(rec: dict) -> tuple[Document | None, str | None]:
    """(Document, atlama_gerekcesi) dondurur."""
    path = _prefer_text_twin(_resolve(rec["local_path"]))
    if not path.exists():
        return None, f"dosya yok: {rec['local_path']}"

    kaynak_turu = settings.source_type_for(rec["category"])
    baglayicilik, otorite = settings.SOURCE_AUTHORITY[kaynak_turu]

    common = dict(
        belge_adi=rec["title"], kaynak_turu=kaynak_turu, baglayicilik=baglayicilik,
        otorite_skoru=otorite, kategori=rec["category"], url=rec["source_url"],
        local_path=str(path),
        karar_no=rec.get("meta_Karar No"),
        karar_tarihi=detail_txt.to_iso(rec.get("meta_Karar Tarihi")),
        konu_ozeti=rec.get("meta_Konu Özeti"),
    )

    suffix = path.suffix.lower()
    if path.name.endswith(".detail.txt"):
        d = detail_txt.parse_detail_txt(path)
        if not d["govde"].strip():
            return None, "govde bos"
        common.update(
            belge_adi=d["baslik"] or rec["title"],
            karar_no=common["karar_no"] or d["karar_no"],
            karar_tarihi=common["karar_tarihi"] or d["karar_tarihi"],
            konu_ozeti=common["konu_ozeti"] or d["konu_ozeti"],
        )
        doc = Document(doc_id=doc_id_for(d["govde"]), text=d["govde"], **common)
        doc.extra["paragraflar"] = d["paragraflar"]
        return doc, None

    if suffix in (".html", ".htm"):
        d = html_resmigazete.load(path)
        if len(d["text"].split()) < 50:
            return None, f"icerik yetersiz ({len(d['text'].split())} kelime)"
        return Document(doc_id=doc_id_for(d["text"]), text=d["text"],
                        rg_tarihi=d["rg_tarihi"], rg_sayisi=d["rg_sayisi"], **common), None

    if suffix == ".pdf":
        d = pdf_text.load(path)
        if d["is_scanned"]:
            return None, f"taranmis goruntu PDF ({d['n_words']} kelime / {d['n_pages']} sayfa)"
        return Document(doc_id=doc_id_for(d["text"]), text=d["text"], **common), None

    return None, f"desteklenmeyen uzanti: {suffix}"


def chunk_document(doc: Document) -> tuple[list[Chunk], str | None]:
    if doc.kaynak_turu in STRUCTURAL_SOURCES:
        if not MADDE_RE.search(doc.text):
            return [], "mevzuat ama MADDE yapisi bulunamadi"
        return chunk_mevzuat(doc), None

    paragraflar = doc.extra.get("paragraflar") or [
        ln.strip() for ln in doc.text.splitlines() if ln.strip()
    ]
    return chunk_karar(doc, paragraflar), None


def run(manifest_path: Path | None = None) -> dict:
    manifest_path = manifest_path or settings.MANIFEST_PATH
    records = json.loads(manifest_path.read_text(encoding="utf-8"))

    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    docs_out = settings.PROCESSED_DIR / "docs.jsonl"
    chunks_out = settings.PROCESSED_DIR / "chunks.jsonl"
    skipped_out = settings.PROCESSED_DIR / "skipped.jsonl"

    seen_doc_ids: set[str] = set()
    n_docs = n_chunks = n_skip = n_dup = 0

    with docs_out.open("w", encoding="utf-8") as fd, \
         chunks_out.open("w", encoding="utf-8") as fc, \
         skipped_out.open("w", encoding="utf-8") as fs:

        for rec in records:
            doc, reason = load_document(rec)
            if doc is None:
                n_skip += 1
                fs.write(json.dumps({**rec, "reason": reason}, ensure_ascii=False) + "\n")
                continue

            if doc.doc_id in seen_doc_ids:
                n_dup += 1
                fs.write(json.dumps({**rec, "reason": f"mukerrer icerik (doc_id={doc.doc_id})"},
                                    ensure_ascii=False) + "\n")
                continue
            seen_doc_ids.add(doc.doc_id)

            chunks, reason = chunk_document(doc)
            if not chunks:
                n_skip += 1
                fs.write(json.dumps({**rec, "reason": reason or "chunk uretilemedi"},
                                    ensure_ascii=False) + "\n")
                continue

            fd.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
            n_docs += 1
            for ch in chunks:
                fc.write(json.dumps(enrich(ch).to_dict(), ensure_ascii=False) + "\n")
            n_chunks += len(chunks)

    return {
        "belge": n_docs, "chunk": n_chunks, "atlanan": n_skip, "mukerrer": n_dup,
        "cikti": str(settings.PROCESSED_DIR),
    }
