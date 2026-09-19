"""Envanter satiri modeli. Yazma islemleri (log + vektor indeksi) hala
kvkk_rag.inventory.store uzerinden yapilir; bu model kapsam filtreli okuma ve
kayit seviyesi yetki dogrulamasi icindir.

Kapsam eslemesi:
  own        -> envanter.created_by = user.id
  assigned   -> envanter.sorumlu_id = user.id OR EXISTS (envanter_denetcileri ...)
  department -> envanter.birim IN (kullanicinin departman adlari)"""
from __future__ import annotations

import sqlite3
from typing import Iterable

from ....inventory.loader import InventoryRow
from ....inventory.store import ALANLAR
from .base import Model, QueryBuilder
from .department import Department
from .scopable import Scopable
from .user import User


class Envanter(Scopable, Model):
    table = "envanter"
    primary_key = "satir_no"
    timestamps = False
    module = "inventory"
    owner_column = "created_by"

    # ---- sorgu seviyesi kapsam ----
    @classmethod
    def scope_assigned(cls, query: QueryBuilder, user: User) -> QueryBuilder:
        return query.where_raw(
            "(envanter.sorumlu_id = ? OR EXISTS ("
            "SELECT 1 FROM envanter_denetcileri d WHERE d.satir_no = envanter.satir_no AND d.user_id = ?))",
            (user.id, user.id))

    @classmethod
    def scope_for_department(cls, query: QueryBuilder, department_ids: Iterable[int]) -> QueryBuilder:
        ids = list(department_ids)
        if not ids:
            return query.where_raw("0 = 1")
        yer = ", ".join("?" * len(ids))
        return query.where_raw(f"envanter.birim IN (SELECT name FROM departments WHERE id IN ({yer}))", ids)

    # ---- kayit seviyesi kapsam ----
    def assigned_to(self, conn: sqlite3.Connection, user: User) -> bool:
        if self.get("sorumlu_id") == user.id:
            return True
        return conn.execute(
            "SELECT 1 FROM envanter_denetcileri WHERE satir_no = ? AND user_id = ?",
            (self.satir_no, user.id)).fetchone() is not None

    def in_departments(self, conn: sqlite3.Connection, department_ids: Iterable[int]) -> bool:
        birim = self.get("birim")
        return bool(birim) and birim in Department.names_for(conn, department_ids)

    # ---- atama ----
    def assign(self, conn: sqlite3.Connection, sorumlu_id: int | None,
               denetci_ids: Iterable[int] | None = None) -> Envanter:
        conn.execute("UPDATE envanter SET sorumlu_id = ? WHERE satir_no = ?", (sorumlu_id, self.satir_no))
        if denetci_ids is not None:
            conn.execute("DELETE FROM envanter_denetcileri WHERE satir_no = ?", (self.satir_no,))
            for uid in set(denetci_ids):
                conn.execute("INSERT OR IGNORE INTO envanter_denetcileri (satir_no, user_id) VALUES (?, ?)",
                             (self.satir_no, uid))
        conn.commit()
        self._attributes["sorumlu_id"] = sorumlu_id
        return self

    def denetci_ids(self, conn: sqlite3.Connection) -> list[int]:
        return [r[0] for r in conn.execute(
            "SELECT user_id FROM envanter_denetcileri WHERE satir_no = ? ORDER BY user_id", (self.satir_no,))]

    # ---- InventoryRow koprusu (denetim motoru dataclass bekler) ----
    def to_inventory_row(self) -> InventoryRow:
        return InventoryRow(satir_no=self.satir_no, **{a: self.get(a) for a in ALANLAR})

    @staticmethod
    def rows(query: QueryBuilder) -> list[InventoryRow]:
        return [e.to_inventory_row() for e in query.order_by("envanter.satir_no").get()]
