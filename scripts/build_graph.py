# Bilgi grafigini kurar: mevzuat + taksonomi + envanter + bulgular.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.graph import build  # noqa: E402


def main() -> None:
    print("Graf kuruluyor...", flush=True)
    out = build.build(rebuild=True)

    print(f"\nMevzuat düğümü : {out['mevzuat_dugum']}")
    print(f"Taksonomi düğümü: {out['taksonomi_dugum']}")
    print(f"Envanter düğümü : {out['envanter_dugum']}")
    print(f"CITES kenarı    : {out['cites_kenar']}")

    st = out["stats"]
    print(f"\n=== TOPLAM: {st['toplam_dugum']} düğüm, {st['toplam_kenar']} kenar ===")
    print("\nDüğüm tipleri:")
    for t, n in sorted(st["nodes"].items(), key=lambda kv: -kv[1]):
        print(f"   {n:>6}  {t}")
    print("\nKenar tipleri:")
    for t, n in sorted(st["edges"].items(), key=lambda kv: -kv[1]):
        print(f"   {n:>6}  {t}")


if __name__ == "__main__":
    main()
