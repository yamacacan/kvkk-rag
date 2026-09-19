"""veri_envanteri.xlsx -> SQLite. Ilk calistirmada otomatik; `force` ile yeniden.
Aktarim EnvanterChanged('ice_aktar') olayi ile denetim gunlugune yazilir."""
from __future__ import annotations

import sqlite3

from ..Services.inventory_service import InventoryService


class EnvanterImport:
    def __init__(self, force: bool = False) -> None:
        self.force = force

    def run(self, conn: sqlite3.Connection, user=None) -> int:
        return InventoryService.ensure_imported(conn, user=user, force=self.force)
