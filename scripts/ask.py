# Uctan uca soru-cevap. --kaynaklar ile LLM cagirmadan sadece retrieval'i gorebilirsin.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.config import settings  # noqa: E402
from kvkk_rag.index import lexical_store  # noqa: E402
from kvkk_rag.llm import prompts  # noqa: E402
from kvkk_rag.retrieval import hybrid  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("soru", nargs="+")
    ap.add_argument("--k", type=int, default=hybrid.PARENT_LIMIT)
    ap.add_argument("--saglayici", default=None, help="gemini | anthropic | ollama")
    ap.add_argument("--kaynaklar", action="store_true", help="LLM cagirmadan sadece kaynaklari listele")
    args = ap.parse_args()

    soru = " ".join(args.soru)
    conn = lexical_store.connect()
    try:
        rows = hybrid.search(soru, conn=conn, limit=args.k)
    finally:
        conn.close()

    if not rows:
        print("Kaynak bulunamadi. Indeks kurulu mu? (scripts/build_index.py)")
        return

    print(f"\n=== {len(rows)} kaynak ===")
    for i, r in enumerate(rows, start=1):
        etiket = r.get("madde_no") and f"m.{r['madde_no']}" or r.get("karar_no") or ""
        print(f"[{i}] {r['baglayicilik']:<13} {r['kaynak_turu']:<18} {etiket:<12} "
              f"skor={r['score']:.4f}  {r['belge_adi'][:60]}")

    if args.kaynaklar:
        return

    llm = __import__("kvkk_rag.llm.factory", fromlist=["get_llm"]).get_llm(args.saglayici)
    print(f"\n=== Cevap ({llm.name}) ===\n")
    print(llm.complete(prompts.build_messages(soru, rows)))


if __name__ == "__main__":
    main()
