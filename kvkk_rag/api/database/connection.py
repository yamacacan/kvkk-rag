"""Tek SQLite baglantisi (Laravel'deki DB facade'inin karsiligi). Her istek kendi
baglantisini acar ve kapatir; gocler surec basina, veritabani yolu basina bir kez
uygulanir. Ayni dosyayi envanter ve mevzuat depolari da kullanir."""
from __future__ import annotations

import sqlite3
import threading
from typing import Iterator

from ...config import settings
from .migrations import migrate

_hazir: set[str] = set()
_kilit = threading.Lock()


def connect() -> sqlite3.Connection:
    from ..app import boot  # gozlemci/dinleyici kaydi; dongusel import olmasin diye burada

    boot()
    settings.SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Istek baglantisi bagimlilik thread'inde acilir, uc/resolver baska bir
    # havuz thread'inde calisabilir (FastAPI/strawberry). CPython sqlite3
    # serialized modda (threadsafety=3) derlendigi icin paylasim guvenlidir.
    conn = sqlite3.connect(settings.SQLITE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    anahtar = str(settings.SQLITE_PATH)
    if anahtar not in _hazir:
        with _kilit:
            if anahtar not in _hazir:
                migrate(conn)
                _hazir.add(anahtar)
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    # FastAPI bagimliligi: istek boyunca tek baglanti, sonunda kapanir.
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def reset() -> None:
    # Testler veritabani yolunu degistirdiginde gocler yeniden uygulansin.
    _hazir.clear()
