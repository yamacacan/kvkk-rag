# Envanter satirlari icin vektor indeksi. Mevzuat indeksiyle ayni LanceDB'de ayri tablo.
# Amac: sohbette "bu veri envanterde var mi?" sorusunu anlamsal olarak cevaplamak ve
# yeni kayit eklenirken benzer/mukerrer kaydi yakalamak.
from __future__ import annotations

from typing import Any

import numpy as np
import pyarrow as pa

from ..index import embedder, vector_store
from .loader import InventoryRow

TABLE = "envanter"

SCHEMA = pa.schema([
    pa.field("satir_no", pa.int64()),
    pa.field("birim", pa.string()),
    pa.field("faaliyet", pa.string()),
    pa.field("veri_kategorisi", pa.string()),
    pa.field("kisisel_veri", pa.string()),
    pa.field("kisi_grubu", pa.string()),
    pa.field("hukuki_sebep", pa.string()),
    pa.field("text", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 768)),
])

# Gomulen metinde alan etiketleri korunur: "Kişisel veri: Parmak izi" ile
# "Faaliyet: Parmak izi ile giris" ayni sey degil, model bunu gormeli.
ALAN_ETIKETI = [
    ("birim", "Birim"), ("faaliyet", "Faaliyet"), ("kisisel_veri", "Kişisel veri"),
    ("veri_kategorisi", "Veri kategorisi"), ("ozel_nitelikli_veri", "Özel nitelikli veri"),
    ("kisi_grubu", "Veri konusu kişi grubu"), ("isleme_amaci", "İşleme amacı"),
    ("hukuki_sebep", "Hukuki sebep"), ("alici_grubu", "Alıcı grubu"),
]


def row_text(row: InventoryRow) -> str:
    parcalar = [f"{etiket}: {getattr(row, alan)}"
                for alan, etiket in ALAN_ETIKETI if getattr(row, alan, None)]
    return " · ".join(parcalar)


def _records(rows: list[InventoryRow], vecs: np.ndarray) -> list[dict[str, Any]]:
    return [{
        "satir_no": int(r.satir_no),
        "birim": r.birim or "", "faaliyet": r.faaliyet or "",
        "veri_kategorisi": r.veri_kategorisi or "", "kisisel_veri": r.kisisel_veri or "",
        "kisi_grubu": r.kisi_grubu or "", "hukuki_sebep": r.hukuki_sebep or "",
        "text": row_text(r), "vector": vecs[i].tolist(),
    } for i, r in enumerate(rows)]


def rebuild(rows: list[InventoryRow]) -> int:
    db = vector_store.connect()
    if not rows:
        if TABLE in db.table_names():
            db.drop_table(TABLE)
        return 0
    vecs = embedder.embed([row_text(r) for r in rows], show_progress=False)
    db.create_table(TABLE, data=_records(rows, vecs), schema=SCHEMA, mode="overwrite")
    return len(rows)


def upsert(rows: list[InventoryRow]) -> None:
    if not rows:
        return
    db = vector_store.connect()
    vecs = embedder.embed([row_text(r) for r in rows])
    recs = _records(rows, vecs)
    if TABLE not in db.table_names():
        db.create_table(TABLE, data=recs, schema=SCHEMA)
        return
    tbl = db.open_table(TABLE)
    tbl.delete(f"satir_no IN ({','.join(str(r['satir_no']) for r in recs)})")
    tbl.add(recs)


def delete(satir_no: int) -> None:
    db = vector_store.connect()
    if TABLE in db.table_names():
        db.open_table(TABLE).delete(f"satir_no = {int(satir_no)}")


def count() -> int:
    db = vector_store.connect()
    return db.open_table(TABLE).count_rows() if TABLE in db.table_names() else 0


def search(query: str, limit: int = 8, where: str | None = None) -> list[dict[str, Any]]:
    db = vector_store.connect()
    if TABLE not in db.table_names():
        return []
    qvec = embedder.embed_query(query)
    q = db.open_table(TABLE).search(qvec).limit(limit)
    if where:
        q = q.where(where, prefilter=True)
    out = []
    for r in q.to_list():
        r.pop("vector", None)
        r["score"] = 1.0 - r.pop("_distance", 0.0) / 2.0
        out.append(r)
    return out


# e5 kosinus skorlari dar bir banda sikisir (0.83-0.86 arasi her sey); mutlak esik
# "Kan grubu"nu "T.C. kimlik" ile eslestiriyordu. Vektor yalnizca ADAY bulur;
# "ayni kayit" karari leksik ortusmeyle verilir. Yanlis "var" demek gercek bir
# boslugu gizler, yanlis "ekleyelim mi" sormak ucuzdur -> kural sikidir.
_GOVDE = 5  # Turkce ekleri icin kok karsilastirmasi: "telefonu" ~ "telefon"

# Her faaliyet adinda gecen genel kelimeler ayirt edici degil: "Kampanya Yönetimi"
# ile "Üyelik Yönetimi" "yönet" uzerinden eslesirse farkli amaclar ayni kayit sanilir.
_GENEL = {"yönet", "işlem", "süreç", "faali", "takip", "kontr", "hizme", "siste",
          "işlet", "yürüt", "sağla", "bilgi", "kişis", "veril", "kayıt", "kaydı"}


def _kokler(s: str) -> set[str]:
    from .normalize import fold
    kok = {t[:_GOVDE] for t in fold(s or "").split() if len(t) >= 4}
    return kok - _GENEL


def _ortusuyor(a: str, b: str) -> bool:
    ka, kb = _kokler(a), _kokler(b)
    return bool(ka and kb and (ka & kb))


def benzer_kayitlar(kisisel_veri: str, birim: str = "", faaliyet: str = "",
                    limit: int = 5) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # (birebir_eslesenler, benzer_adaylar) dondurur. Birebir: veri VE faaliyet ortusur.
    sorgu = " · ".join(p for p in (
        f"Birim: {birim}" if birim else "",
        f"Faaliyet: {faaliyet}" if faaliyet else "",
        f"Kişisel veri: {kisisel_veri}",
    ) if p)
    adaylar = search(sorgu, limit=max(limit, 10))
    birebir = [r for r in adaylar
               if _ortusuyor(kisisel_veri, r["kisisel_veri"])
               and (not faaliyet or _ortusuyor(faaliyet, r["faaliyet"]))]
    return birebir[:limit], adaylar[:limit]
