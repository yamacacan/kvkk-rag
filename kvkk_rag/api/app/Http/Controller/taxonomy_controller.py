from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends

from .....inventory import taxonomy as inv_taxonomy
from ....database.connection import get_db
from ...Services.inventory_service import InventoryService
from ..Middleware.authenticate import authenticate
from .base import Controller, route


class TaxonomyController(Controller):
    prefix = "/api/taxonomy"
    tags = ["taksonomi"]
    middleware = (authenticate,)

    @route("GET", "", permission="taxonomy.view")
    def index(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Acilir listeler seeder'lardan; listede yoksa kullanici "Diğer(...)" yazar.
        InventoryService.ensure_imported(conn)
        mevcut = {alan: InventoryService.distinct(conn, alan)
                  for alan in ("birim", "faaliyet", "veri_kategorisi", "kisi_grubu")}
        return {
            "kanonik": {
                "veri_kategorisi": inv_taxonomy.values("veri_kategorisi"),
                # ayni ad iki grupta olabilir; duz listede tekillestirilir, ayrinti asagida
                "hukuki_sebep": list(dict.fromkeys(inv_taxonomy.values("hukuki_sebep"))),
                "isleme_amaci": inv_taxonomy.values("isleme_amaci"),
                "alici_grubu": inv_taxonomy.values("alici_grubu"),
                "teknik_tedbir": inv_taxonomy.values("teknik_tedbir"),
                "idari_tedbir": inv_taxonomy.values("idari_tedbir"),
            },
            "envanterden": mevcut,
            # madde grubuyla (m.5 genel / m.6 ozel nitelikli / m.28 istisna) acilir liste
            "hukuki_sebep_detay": inv_taxonomy.hukuki_sebep_detay(),
            "ozel_nitelikli_kategoriler": sorted(inv_taxonomy.OZEL_NITELIKLI_KATEGORILER),
            "diger_kalibi": "Diğer(açıklama)",
        }
