"""1. kademe: fonksiyonel izin. Ad bicimi `modul.aksiyon` (findings.view, reports.export)."""
from __future__ import annotations

import sqlite3

from .base import Model

GUARD = "api"


def parse(name: str) -> tuple[str, str]:
    if name.count(".") != 1:
        raise ValueError(f"İzin adı 'modul.aksiyon' biçiminde olmalı: {name!r}")
    module, action = name.split(".")
    if not module or not action:
        raise ValueError(f"İzin adı 'modul.aksiyon' biçiminde olmalı: {name!r}")
    return module, action


class Permission(Model):
    table = "permissions"
    fillable = ("name", "guard_name", "module", "action", "description")

    @classmethod
    def find_by_name(cls, conn: sqlite3.Connection, name: str,
                     guard: str = GUARD) -> Permission | None:
        return cls.query(conn).where("name", name).where("guard_name", guard).first()

    @classmethod
    def find_or_create(cls, conn: sqlite3.Connection, name: str,
                       description: str | None = None, guard: str = GUARD) -> Permission:
        mevcut = cls.find_by_name(conn, name, guard)
        if mevcut:
            if description and mevcut.description != description:
                mevcut.update(conn, description=description)
            return mevcut
        module, action = parse(name)
        return cls.create(conn, name=name, guard_name=guard, module=module,
                          action=action, description=description)

    @classmethod
    def by_module(cls, conn: sqlite3.Connection) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        for p in cls.query(conn).order_by("module").order_by("action").get():
            out.setdefault(p.module, []).append(p.to_dict())
        return out
