"""Envanter veri girisi / aktarimi -> denetim gunlugu (inventory.*). Satir bazli
once/sonra farki envanter_log'da da tutulur; burasi kurum geneli denetim izidir."""
from __future__ import annotations

from ..Events import EnvanterChanged
from ..Models.audit_log import AuditLog

EYLEM = {
    "olustur": "inventory.create", "guncelle": "inventory.update", "sil": "inventory.delete",
    "ice_aktar": "inventory.import", "disa_aktar": "inventory.export", "ata": "inventory.assign",
    "yeniden_indeksle": "inventory.reindex",
}


class LogEnvanterChange:
    def handle(self, event: EnvanterChanged) -> None:
        eylem = EYLEM.get(event.islem, f"inventory.{event.islem}")
        etiket = event.etiket
        if not etiket and event.satir_no is not None:
            kaynak = event.sonra or event.once or {}
            parca = [p for p in (kaynak.get("birim"), kaynak.get("kisisel_veri")) if p]
            etiket = f"#{event.satir_no}" + (f" · {' / '.join(parca)}" if parca else "")
        if not etiket and event.adet is not None:
            etiket = f"{event.adet} satır"
        sonra = event.sonra
        if sonra is None and event.adet is not None:
            sonra = {"adet": event.adet}
        AuditLog.record(event.conn, eylem, actor=event.user, target_type="Envanter",
                        target_id=event.satir_no, target_label=etiket,
                        before=event.once, after=sonra, ip=event.ip)
