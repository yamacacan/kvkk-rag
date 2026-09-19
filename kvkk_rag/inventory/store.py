# Yazilabilir envanter deposu. xlsx bir kez ice aktarilir, sonrasi SQLite uzerinden.
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from .loader import COLUMNS, InventoryRow, load as load_xlsx

ALANLAR = [
    "birim", "faaliyet", "veri_kategorisi", "kisisel_veri", "ozel_nitelikli_veri",
    "kisi_grubu", "isleme_amaci", "hukuki_sebep", "saklama_suresi", "alici_grubu",
    "yurt_disi_aktarim", "teknik_tedbir", "idari_tedbir", "imha_yontemi",
    "kayit_ortami", "periyodik_imha_suresi", "yurt_disi_ulke", "aktarim_amaci",
    "veri_isleyen",
]

# Sahiplik/atama sutunlari: RBAC kapsam katmani (own / assigned) bunlari kullanir.
META_ALANLAR = ("created_by", "sorumlu_id")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS envanter (
    satir_no   INTEGER PRIMARY KEY AUTOINCREMENT,
    {', '.join(f'{a} TEXT' for a in ALANLAR)},
    kaynak     TEXT NOT NULL DEFAULT 'xlsx',
    olusturma  TEXT,
    guncelleme TEXT,
    notlar     TEXT,
    created_by INTEGER,
    sorumlu_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_env_birim ON envanter(birim);
CREATE INDEX IF NOT EXISTS idx_env_faaliyet ON envanter(faaliyet);

-- assigned kapsami: satira ekip uyesi/denetci olarak atanan kullanicilar
CREATE TABLE IF NOT EXISTS envanter_denetcileri (
    satir_no INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    PRIMARY KEY (satir_no, user_id)
);

CREATE TABLE IF NOT EXISTS envanter_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    satir_no INTEGER NOT NULL,
    islem   TEXT NOT NULL,
    onceki  TEXT,
    sonraki TEXT,
    zaman   TEXT NOT NULL,
    kaynak  TEXT,
    kullanici_id INTEGER
);
"""


def _vektor_guncelle(row: InventoryRow | None) -> None:
    # Vektor indeksi turetilmis veridir; hatasi envanter yazimini geri almamali.
    if row is None:
        return
    try:
        from . import vector
        vector.upsert([row])
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("Envanter vektor guncellemesi atlandi: %s", e)


def _vektor_sil(satir_no: int) -> None:
    try:
        from . import vector
        vector.delete(satir_no)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("Envanter vektor silme atlandi: %s", e)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migrate(conn: sqlite3.Connection) -> list[str]:
    # CREATE TABLE IF NOT EXISTS mevcut tabloyu degistirmez; sonradan eklenen
    # alanlar icin ALTER gerekir.
    var = {r[1] for r in conn.execute("PRAGMA table_info(envanter)")}
    eklenen = [a for a in ALANLAR if a not in var]
    for a in eklenen:
        conn.execute(f"ALTER TABLE envanter ADD COLUMN {a} TEXT")
    for a in META_ALANLAR:
        if a not in var:
            conn.execute(f"ALTER TABLE envanter ADD COLUMN {a} INTEGER")
            eklenen.append(a)
    log_var = {r[1] for r in conn.execute("PRAGMA table_info(envanter_log)")}
    if "kullanici_id" not in log_var:
        conn.execute("ALTER TABLE envanter_log ADD COLUMN kullanici_id INTEGER")
        eklenen.append("envanter_log.kullanici_id")
    if eklenen:
        conn.commit()
    return eklenen


def connect() -> sqlite3.Connection:
    settings.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def satir_sayisi(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM envanter").fetchone()[0]


def import_xlsx(conn: sqlite3.Connection, force: bool = False) -> int:
    if satir_sayisi(conn) and not force:
        return 0
    if force:
        conn.executescript("DELETE FROM envanter; DELETE FROM envanter_log;")

    rows, _ = load_xlsx()
    data = [tuple(getattr(r, a) for a in ALANLAR) + ("xlsx", _now(), _now())
            for r in rows]
    conn.executemany(
        f"INSERT INTO envanter ({', '.join(ALANLAR)}, kaynak, olusturma, guncelleme) "
        f"VALUES ({','.join('?' * (len(ALANLAR) + 3))})", data)
    conn.commit()
    return len(data)


def _to_row(r: sqlite3.Row) -> InventoryRow:
    return InventoryRow(satir_no=r["satir_no"], **{a: r[a] for a in ALANLAR})


def all_rows(conn: sqlite3.Connection) -> list[InventoryRow]:
    return [_to_row(r) for r in conn.execute("SELECT * FROM envanter ORDER BY satir_no")]


def get(conn: sqlite3.Connection, satir_no: int) -> InventoryRow | None:
    r = conn.execute("SELECT * FROM envanter WHERE satir_no = ?", (satir_no,)).fetchone()
    return _to_row(r) if r else None


def create(conn: sqlite3.Connection, veri: dict[str, Any], kaynak: str = "elle",
           meta: dict[str, Any] | None = None, kullanici_id: int | None = None) -> int:
    # meta: created_by / sorumlu_id gibi sahiplik sutunlari (RBAC kapsami icin)
    alanlar = [a for a in ALANLAR if a in veri]
    ek = {k: v for k, v in (meta or {}).items() if k in META_ALANLAR and v is not None}
    sutunlar = alanlar + list(ek) + ["kaynak", "olusturma", "guncelleme"]
    sql = (f"INSERT INTO envanter ({', '.join(sutunlar)}) "
           f"VALUES ({','.join('?' * len(sutunlar))})")
    cur = conn.execute(sql, [veri.get(a) for a in alanlar] + list(ek.values()) + [kaynak, _now(), _now()])
    satir_no = cur.lastrowid
    conn.execute("INSERT INTO envanter_log (satir_no, islem, sonraki, zaman, kaynak, kullanici_id) "
                 "VALUES (?,?,?,?,?,?)",
                 (satir_no, "olustur", json.dumps(veri, ensure_ascii=False), _now(), kaynak, kullanici_id))
    conn.commit()
    _vektor_guncelle(get(conn, satir_no))
    return satir_no


def update(conn: sqlite3.Connection, satir_no: int, veri: dict[str, Any],
           kaynak: str = "elle", kullanici_id: int | None = None) -> InventoryRow | None:
    mevcut = get(conn, satir_no)
    if not mevcut:
        return None
    alanlar = [a for a in ALANLAR if a in veri]
    if alanlar:
        conn.execute(
            f"UPDATE envanter SET {', '.join(f'{a} = ?' for a in alanlar)}, guncelleme = ? "
            f"WHERE satir_no = ?",
            [veri[a] for a in alanlar] + [_now(), satir_no])
        conn.execute(
            "INSERT INTO envanter_log (satir_no, islem, onceki, sonraki, zaman, kaynak, kullanici_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (satir_no, "guncelle",
             json.dumps({a: getattr(mevcut, a) for a in alanlar}, ensure_ascii=False),
             json.dumps({a: veri[a] for a in alanlar}, ensure_ascii=False), _now(), kaynak, kullanici_id))
        conn.commit()
    row = get(conn, satir_no)
    if alanlar:
        _vektor_guncelle(row)
    return row


def delete(conn: sqlite3.Connection, satir_no: int, kullanici_id: int | None = None) -> bool:
    mevcut = get(conn, satir_no)
    if not mevcut:
        return False
    conn.execute("DELETE FROM envanter WHERE satir_no = ?", (satir_no,))
    conn.execute("DELETE FROM envanter_denetcileri WHERE satir_no = ?", (satir_no,))
    conn.execute("INSERT INTO envanter_log (satir_no, islem, onceki, zaman, kaynak, kullanici_id) "
                 "VALUES (?,?,?,?,?,?)",
                 (satir_no, "sil", json.dumps(mevcut.to_dict(), ensure_ascii=False), _now(), "elle", kullanici_id))
    conn.commit()
    _vektor_sil(satir_no)
    return True


def distinct(conn: sqlite3.Connection, alan: str) -> list[str]:
    if alan not in ALANLAR:
        return []
    rs = conn.execute(
        f"SELECT DISTINCT {alan} FROM envanter WHERE {alan} IS NOT NULL AND {alan} != '' "
        f"ORDER BY {alan}").fetchall()
    return [r[0] for r in rs]


def history(conn: sqlite3.Connection, satir_no: int | None = None, limit: int = 50) -> list[dict]:
    sql = "SELECT * FROM envanter_log"
    params: list[Any] = []
    if satir_no is not None:
        sql += " WHERE satir_no = ?"
        params.append(satir_no)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params)]
