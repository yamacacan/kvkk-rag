"""Faaliyet belgesi otomatik yenilendi / uretilemedi -> denetim gunlugu (aktor: sistem)."""
from __future__ import annotations

from ....compliance import generate as comp_generate
from ..Events import FaaliyetBelgesiYenilendi
from ..Models.audit_log import AuditLog


class LogFaaliyetBelgesi:
    def handle(self, event: FaaliyetBelgesiYenilendi) -> None:
        b = event.belge
        ad = comp_generate.BELGE_ADI.get(b.sablon, b.sablon)
        if event.sonuc == "uretildi":
            AuditLog.record(event.conn, "documents.auto_refresh", target_type="FaaliyetBelgesi", target_id=b.id,
                            target_label=f"{ad} · {b.faaliyet}", after={"satir": b.get("satir"), "boyut": b.get("boyut")})
        else:
            AuditLog.record(event.conn, "documents.auto_failed", target_type="FaaliyetBelgesi", target_id=b.id,
                            target_label=f"{ad} · {b.faaliyet}", after={"hata": b.get("hata")})
