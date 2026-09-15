"""Korpusu chunk'lar: data/raw/manifest.json -> data/processed/{docs,chunks,skipped}.jsonl

Kullanim (konteyner icinde):
    docker compose run --rm app python scripts/ingest_all.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json  # noqa: E402

from kvkk_rag.config import settings  # noqa: E402
from kvkk_rag.index import embedder  # noqa: E402
from kvkk_rag.ingest import pipeline  # noqa: E402


def main() -> None:
    print(f"Cihaz: {embedder.device_info()}")
    print(f"Manifest: {settings.MANIFEST_PATH}")

    stats = pipeline.run()
    print(f"\nBelge: {stats['belge']}  Chunk: {stats['chunk']}  "
          f"Atlanan: {stats['atlanan']}  Mukerrer: {stats['mukerrer']}")

    chunks_path = settings.PROCESSED_DIR / "chunks.jsonl"
    by_source: Counter = Counter()
    by_level: Counter = Counter()
    over_limit = 0
    with chunks_path.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            by_source[c["kaynak_turu"]] += 1
            by_level[c["level"]] += 1
            if c["char_len"] > 1600:
                over_limit += 1

    print("\nKaynak turune gore:")
    for k, v in by_source.most_common():
        bag, otorite = settings.SOURCE_AUTHORITY[k]
        print(f"  {v:>6}  {k:<20} {bag:<13} otorite={otorite}")
    print(f"\nSeviye: {dict(by_level)}")
    print(f"1600 karakteri asan chunk: {over_limit}")

    skipped = settings.PROCESSED_DIR / "skipped.jsonl"
    reasons: Counter = Counter()
    with skipped.open(encoding="utf-8") as f:
        for line in f:
            reasons[json.loads(line)["reason"].split("(")[0].strip()] += 1
    if reasons:
        print("\nAtlama gerekceleri:")
        for r, n in reasons.most_common():
            print(f"  {n:>4}  {r}")


if __name__ == "__main__":
    main()
