# Laravel seeder dosyalarindan kanonik KVKK taksonomilerini cikarir.
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SRC = Path(__file__).resolve().parent.parent / "data" / "inventory"

FILES = {
    "veri_kategorisi": "veri_kategorileri.txt",
    "hukuki_sebep":    "Hukuki sebepler.txt",
    "alici_grubu":     "AlıcıGrupları.txt",
    "teknik_tedbir":   "Teknik Tedbirler.txt",
    "idari_tedbir":    "İdari tedbirler seedar.txt",
    "isleme_amaci":    "İşleme amaçları seeder.txt",
}

# PHP tek tirnakli string: kacis yalnizca \' ve \\ olabilir
NAME = re.compile(r"'name'\s*=>\s*'((?:[^'\\]|\\.)*)'", re.S)
DESC = re.compile(r"'description'\s*=>\s*'((?:[^'\\]|\\.)*)'", re.S)


def unescape(s: str) -> str:
    return s.replace("\\'", "'").replace("\\\\", "\\").strip()


def parse(path: Path) -> list[dict]:
    txt = path.read_text(encoding="utf-8")
    names = [unescape(n) for n in NAME.findall(txt)]
    descs = [unescape(d) for d in DESC.findall(txt)]
    return [{"ad": n, "aciklama": descs[i] if i < len(descs) else ""}
            for i, n in enumerate(names)]


def main() -> None:
    out: dict[str, list[dict]] = {}
    for key, fname in FILES.items():
        path = SRC / fname
        if not path.exists():
            print(f"[ATLA] {fname} yok")
            continue
        items = parse(path)
        out[key] = items
        ornek = items[0]["ad"][:58] if items else "-"
        print(f"{key:<15} {len(items):>3} deger | {ornek}")

    # Hukuki sebeplerde 'description' alani grup bilgisi tasiyor
    if "hukuki_sebep" in out:
        gruplar: dict[str, int] = {}
        for it in out["hukuki_sebep"]:
            gruplar[it["aciklama"]] = gruplar.get(it["aciklama"], 0) + 1
        print("\nhukuki sebep gruplari:")
        for g, n in gruplar.items():
            print(f"   {n:>2}  {g}")

    dest = SRC / "taksonomi.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
