# Envanter (SQLite) -> LanceDB "envanter" tablosu. Sohbetin "envanterde var mi" kontrolu icin.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.index import embedder  # noqa: E402
from kvkk_rag.inventory import store, vector  # noqa: E402


def main() -> None:
    print(f"Cihaz: {embedder.device_info()}")
    conn = store.connect()
    try:
        store.import_xlsx(conn)
        rows = store.all_rows(conn)
    finally:
        conn.close()
    n = vector.rebuild(rows)
    print(f"Envanter vektor indeksi: {n} satir -> LanceDB '{vector.TABLE}'")

    ornek = vector.search("çalışanların parmak izi ile giriş çıkış takibi", limit=3)
    if ornek:
        print("\nOrnek sorgu -> en yakin 3 kayit:")
        for r in ornek:
            print(f"  {r['score']:.3f}  #{r['satir_no']}  {r['kisisel_veri'][:30]:<30} | {r['faaliyet'][:40]}")


if __name__ == "__main__":
    main()
