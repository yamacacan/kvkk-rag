# Envanter uyum denetimi raporu.
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.config import settings  # noqa: E402
from kvkk_rag.inventory import audit, loader  # noqa: E402


def main() -> None:
    rows, eksik_sutun = loader.load()
    print(f"Envanter: {len(rows)} satır — {settings.INVENTORY_PATH.name}")
    if eksik_sutun:
        print(f"Dosyada bulunmayan sütunlar: {eksik_sutun}")

    print("\n=== NORMALİZASYON ===")
    norm = audit.normalization_report(rows)
    for alan, r in norm.items():
        if not r["benzersiz"]:
            continue
        print(f"\n{alan}: {r['benzersiz']} benzersiz değer — {r['ozet']}")
        for s in r["sorunlu"]:
            hedef = s["kanonik"] or "— EŞLEŞMEDİ —"
            print(f"   [{s['yontem']} {s['guven']}] {s['ham'][:58]}")
            print(f"      -> {str(hedef)[:70]}")

    print("\n=== UYUM DENETİMİ ===")
    rapor = audit.audit(rows)
    print(f"Satır: {rapor['satir']}  Bulgu: {rapor['bulgu']}  "
          f"Temiz satır: {rapor['temiz_satir']}  Uyum oranı: %{rapor['uyum_orani']*100:.1f}")
    print(f"\nSeviyeye göre: {rapor['seviye']}")
    print("\nKurala göre:")
    kod_basliklari = {f.kod: f.baslik for f in rapor["findings"]}
    for kod, n in sorted(rapor["kod"].items()):
        print(f"   {kod}  {n:>5}  {kod_basliklari.get(kod, '')}")

    print("\nÖrnek bulgular:")
    gorulen = set()
    for f in rapor["findings"]:
        if f.kod in gorulen:
            continue
        gorulen.add(f.kod)
        print(f"\n  [{f.seviye.upper()}] {f.kod} · satır {f.satir_no} · {f.baslik}")
        print(f"    {f.aciklama[:150]}")
        print(f"    Dayanak: {f.dayanak}")

    out = settings.DATA_DIR / "inventory" / "audit_report.json"
    out.write_text(json.dumps({
        "ozet": {k: v for k, v in rapor.items() if k != "findings"},
        "normalizasyon": norm,
        "bulgular": [f.to_dict() for f in rapor["findings"][:2000]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
