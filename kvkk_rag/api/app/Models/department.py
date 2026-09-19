"""Departman (birim). Envanterdeki `birim` metniyle ad uzerinden eslesir; kullanici
tekil (users.department_id) veya coklu (user_departments) departmana bagli olabilir."""
from __future__ import annotations

import sqlite3
from typing import Iterable

from .base import Model


class Department(Model):
    table = "departments"
    fillable = ("name", "description")

    @classmethod
    def find_by_name(cls, conn: sqlite3.Connection, name: str) -> Department | None:
        return cls.query(conn).where("name", name).first()

    @classmethod
    def find_or_create(cls, conn: sqlite3.Connection, name: str) -> Department:
        return cls.first_or_create(conn, {"name": name.strip()})

    @classmethod
    def names_for(cls, conn: sqlite3.Connection, ids: Iterable[int]) -> list[str]:
        return cls.query(conn).where_in("id", ids).pluck("name")

    def user_ids(self, conn: sqlite3.Connection) -> list[int]:
        return [r[0] for r in conn.execute(
            "SELECT id FROM users WHERE department_id = ? "
            "UNION SELECT user_id FROM user_departments WHERE department_id = ?",
            (self.id, self.id))]

    def envanter_sayisi(self, conn: sqlite3.Connection) -> int:
        var = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if "envanter" not in var:
            return 0
        return int(conn.execute("SELECT COUNT(*) FROM envanter WHERE birim = ?", (self.name,)).fetchone()[0])
