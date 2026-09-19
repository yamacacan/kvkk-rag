"""Acik riza kaydi olustu/guncellendi/silindi -> denetim gunlugu (TC kimlik maskeli)."""
from __future__ import annotations

from ..Events import ConsentChanged
from ..Models.audit_log import AuditLog
from ..Models.consent import tc_maskele

EYLEM = {"olustur": "consents.create", "guncelle": "consents.update", "sil": "consents.delete"}


def _maskele(d):
    if not d:
        return d
    d = dict(d)
    if d.get("tc_kimlik"):
        d["tc_kimlik"] = tc_maskele(str(d["tc_kimlik"]))
    return d


class LogConsentChange:
    def handle(self, event: ConsentChanged) -> None:
        c = event.consent
        AuditLog.record(event.conn, EYLEM.get(event.islem, f"consents.{event.islem}"), actor=event.user,
                        target_type="AcikRiza", target_id=c.id,
                        target_label=f"{c.ad_soyad} · {c.faaliyet}",
                        before=_maskele(event.once), after=_maskele(event.sonra), ip=event.ip)
