"""Olay veriyolu (Laravel Event / Listener).

Olaylar dataclass'tir; dinleyiciler `handle(event)` metodu olan nesnelerdir ve
Listeners/__init__.py'de `listen(Olay, Dinleyici())` ile eslenir. `dispatch(olay)`
olayin sinifina VE ust siniflarina kayitli dinleyicileri sirayla cagirir; boylece
`listen(Event, X())` tum olaylari yakalar (joker dinleyici).

Veritabani gerektiren olaylar acik `conn` tasir: istek icinden gelenler istegin
baglantisini, worker'dan gelenler isin kendi baglantisini kullanir. Bir dinleyici
patlarsa loglanir, diger dinleyiciler ve olayi ureten akis etkilenmez."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("kvkk_rag.api.events")

_dinleyiciler: dict[type, list[Any]] = {}


class Event:
    pass


# ---- kimlik ----
@dataclass
class Login(Event):
    user: Any
    conn: sqlite3.Connection


@dataclass
class Logout(Event):
    user: Any
    conn: sqlite3.Connection
    ip: str | None = None


@dataclass
class PasswordResetRequested(Event):
    user: Any
    reset_url: str


@dataclass
class PasswordReset(Event):
    user: Any
    conn: sqlite3.Connection


# ---- yetki ----
@dataclass
class PermissionsChanged(Event):
    # Rol izinleri veya kapsamlar degisti; onbellek surumu artirildi
    reason: str
    version: int = 0
    meta: dict[str, Any] = field(default_factory=dict)


# ---- envanter (veri girisi / aktarimi) ----
@dataclass
class EnvanterChanged(Event):
    """islem: olustur | guncelle | sil | ice_aktar | disa_aktar | ata | yeniden_indeksle"""
    islem: str
    conn: sqlite3.Connection
    user: Any = None
    satir_no: int | None = None
    once: dict[str, Any] | None = None
    sonra: dict[str, Any] | None = None
    adet: int | None = None
    etiket: str | None = None
    ip: str | None = None


@dataclass
class EnvanterIslemiTamamlandi(Event):
    """Kuyruktaki envanter isi (disa/ice aktarim, yeniden indeksleme) bitti."""
    islem: Any            # EnvanterIslemi
    conn: sqlite3.Connection
    duration_ms: int = 0


@dataclass
class EnvanterIslemiBasarisiz(Event):
    islem: Any
    error: str
    conn: sqlite3.Connection


# ---- faaliyet belgeleri / kurum profili / acik riza ----
@dataclass
class KurumProfiliGuncellendi(Event):
    user: Any
    conn: sqlite3.Connection
    once: dict[str, Any] | None = None
    sonra: dict[str, Any] | None = None


@dataclass
class FaaliyetBelgesiYenilendi(Event):
    """Kuyruktaki is bir faaliyet belgesini yeniden uretti (sonuc: uretildi | hata)."""
    belge: Any
    sonuc: str
    conn: sqlite3.Connection


@dataclass
class ConsentChanged(Event):
    """islem: olustur | guncelle | sil"""
    islem: str
    consent: Any
    user: Any
    conn: sqlite3.Connection
    once: dict[str, Any] | None = None
    sonra: dict[str, Any] | None = None
    ip: str | None = None


# ---- belgeler ----
@dataclass
class DocumentRequested(Event):
    document: Any          # GeneratedDocument
    user: Any
    conn: sqlite3.Connection
    ip: str | None = None


@dataclass
class DocumentGenerated(Event):
    document: Any
    conn: sqlite3.Connection
    duration_ms: int = 0


@dataclass
class DocumentFailed(Event):
    document: Any
    error: str
    conn: sqlite3.Connection


# ---- kuyruk ----
@dataclass
class JobProcessed(Event):
    job_id: int
    job: str
    duration_ms: int
    conn: sqlite3.Connection
    user_id: int | None = None


@dataclass
class JobFailed(Event):
    job_id: int
    job: str
    error: str
    conn: sqlite3.Connection
    user_id: int | None = None


# ---- arayuz ----
@dataclass
class PageViewed(Event):
    user: Any
    conn: sqlite3.Connection
    path: str
    name: str | None = None
    title: str | None = None
    ip: str | None = None


# ---- veriyolu ----
def listen(event_cls: type, listener: Any) -> None:
    listem = _dinleyiciler.setdefault(event_cls, [])
    if not any(type(l) is type(listener) for l in listem):
        listem.append(listener)


def listeners(event_cls: type) -> list[Any]:
    out: list[Any] = []
    for base in event_cls.__mro__:
        if base is object:
            continue
        out.extend(_dinleyiciler.get(base, ()))
    return out


def dispatch(event: Event) -> int:
    """Dinleyicileri cagirir; kac dinleyicinin calistigini doner."""
    n = 0
    for l in listeners(type(event)):
        handler: Callable[[Event], None] = getattr(l, "handle", l)
        try:
            handler(event)
            n += 1
        except Exception:  # noqa: BLE001 - bir dinleyici digerlerini ve ana akisi dusurmesin
            logger.exception("Dinleyici %s, %s olayinda basarisiz", type(l).__name__, type(event).__name__)
    return n


def forget_all() -> None:
    _dinleyiciler.clear()
