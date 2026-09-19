"""Belge hazir / hata -> isteyen kullaniciya uygulama ici bildirim (header zili)."""
from __future__ import annotations

import json

from ..Events import DocumentFailed, DocumentGenerated
from ..Models.notification import Notification


class NotifyDocumentOwner:
    def handle(self, event: DocumentGenerated | DocumentFailed) -> None:
        b = event.document
        ad = b.get("sablon_adi") or b.sablon
        if isinstance(event, DocumentGenerated):
            ek = ""
            if b.get("tur") == "zip":
                ek = f" · {b.get('uretilen') or 0} belge"
            elif b.get("kalan"):
                try:
                    n = len(json.loads(b.kalan))
                except ValueError:
                    n = 0
                ek = f" · {n} alan boş kaldı" if n else ""
            Notification.send(
                event.conn, b.user_id, "documents.ready", level="ok",
                title="Belgeniz hazır", body=f"{ad}{ek}. İndirmek için tıklayın.",
                link=f"/belgeler?belge={b.id}",
                data={"belge_id": b.id, "ad": b.get("ad"), "tur": b.get("tur")})
        else:
            Notification.send(
                event.conn, b.user_id, "documents.failed", level="hata",
                title="Belge üretilemedi", body=f"{ad}: {event.error}",
                link="/belgeler", data={"belge_id": b.id})
