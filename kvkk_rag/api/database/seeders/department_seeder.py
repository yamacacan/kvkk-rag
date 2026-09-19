"""Departmanlar envanterdeki `birim` degerlerinden turetilir: department kapsami
ilk gunden anlamli olsun. Yeni birimler sonradan API ile eklenir."""
from __future__ import annotations

import sqlite3

from ...app.Models.department import Department
from ...app.Services.inventory_service import InventoryService


class DepartmentSeeder:
    @staticmethod
    def run(conn: sqlite3.Connection) -> int:
        InventoryService.ensure_imported(conn)  # xlsx henuz alinmadiysa once o
        eklenen = 0
        for (birim,) in conn.execute(
                "SELECT DISTINCT birim FROM envanter WHERE birim IS NOT NULL AND TRIM(birim) != '' ORDER BY birim"):
            if Department.find_by_name(conn, birim.strip()) is None:
                Department.create(conn, name=birim.strip())
                eklenen += 1
        return eklenen
