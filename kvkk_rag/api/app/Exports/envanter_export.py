"""Envanter -> xlsx (Laravel `Excel::download(new EnvanterExport(...))` okunusu)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import Response

from ....inventory import excel as inv_excel
from ....inventory.loader import InventoryRow

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class EnvanterExport:
    def __init__(self, rows: list[InventoryRow], kurum: str = "") -> None:
        self.rows = rows
        self.kurum = kurum

    def build(self) -> bytes:
        return inv_excel.build(self.rows, kurum=self.kurum)

    def download(self, filename: str) -> Response:
        return Response(
            content=self.build(), media_type=XLSX,
            headers={"Content-Disposition": f'attachment; filename="{quote(filename)}"'})
