"""Uygulama katmani (Laravel `app/`). boot(): gozlemci ve dinleyici kayitlari
(AppServiceProvider::boot + EventServiceProvider). Idempotenttir; hem API
bootstrap'i hem konsol komutlari hem de dogrudan DB baglantisi cagirir."""
from __future__ import annotations

_booted = False


def boot() -> None:
    global _booted
    if _booted:
        return
    from . import Listeners, Observers

    Observers.register()
    Listeners.register()
    _booted = True
