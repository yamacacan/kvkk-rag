# chunks.jsonl -> LanceDB (dense, sadece child) + SQLite FTS5 (leksik, hepsi)
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.config import settings  # noqa: E402
from kvkk_rag.index import embedder, lexical_store, vector_store  # noqa: E402


def main() -> None:
    chunks_path = settings.PROCESSED_DIR / "chunks.jsonl"
    if not chunks_path.exists():
        sys.exit(f"Once ingest calistirin: {chunks_path} yok")

    chunks = [json.loads(l) for l in chunks_path.open(encoding="utf-8")]
    children = [c for c in chunks if c["level"] == "child"]
    print(f"Cihaz: {embedder.device_info()}")
    print(f"Toplam chunk: {len(chunks)} (gomulecek child: {len(children)})")

    # token_len'i doldur ve 480 uzerini isaretle (BERTurk-STS 512 siniri)
    asiri = 0
    for c in children:
        c["token_len"] = embedder.token_len(c["text"])
        if c["token_len"] > settings.EMBED_MAX_TOKENS:
            asiri += 1
    if asiri:
        print(f"UYARI: {asiri} child {settings.EMBED_MAX_TOKENS} token sinirini asiyor (kirpilacak)")

    print("Gomme uretiliyor...")
    vectors = embedder.embed([c["text"] for c in children], show_progress=True)
    vector_store.write(children, vectors, overwrite=True)
    print(f"LanceDB: {vector_store.count()} vektor")

    conn = lexical_store.connect()
    # Semantik chunk sinirlari embedding modeline bagli; model degisince eski
    # chunk_id'ler bayat kalir ve LanceDB ile SQLite birbirini tutmaz.
    conn.executescript("DELETE FROM chunks; DELETE FROM chunks_fts;")
    n = lexical_store.upsert(conn, chunks)
    print(f"SQLite FTS5: {n} chunk -> {lexical_store.count(conn)}")
    conn.close()


if __name__ == "__main__":
    main()
