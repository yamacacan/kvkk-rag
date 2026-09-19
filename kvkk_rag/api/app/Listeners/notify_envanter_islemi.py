"""Envanter arka plan isi bitti / basarisiz -> isi baslatan kullaniciya bildirim +
(hata durumunda) denetim gunlugu. Basarili disa/ice aktarim gunluge EnvanterChanged
uzerinden zaten yazilir."""
from __future__ import annotations

from ..Events import EnvanterIslemiBasarisiz, EnvanterIslemiTamamlandi
from ..Models.audit_log import AuditLog
from ..Models.envanter_islemi import DISA_AKTAR, ICE_AKTAR, TUR_ADI
from ..Models.notification import Notification
from ..Models.user import User


class NotifyEnvanterIslemi:
    def handle(self, event: EnvanterIslemiTamamlandi | EnvanterIslemiBasarisiz) -> None:
        i = event.islem
        ad = TUR_ADI.get(i.tur, i.tur)
        link = f"/envanter?islem={i.id}"
        if isinstance(event, EnvanterIslemiTamamlandi):
            s = i.result
            if i.tur == DISA_AKTAR:
                Notification.send(event.conn, i.user_id, "inventory.export_ready", level="ok",
                                  title="Excel dosyanız hazır",
                                  body=f"{i.get('ad')} · {s.get('satir', 0)} satır. İndirmek için tıklayın.",
                                  link=link, data={"islem_id": i.id, "ad": i.get("ad")})
            elif i.tur == ICE_AKTAR:
                ek = f", {s['atlanan']} satır kapsam dışı (atlandı)" if s.get("atlanan") else ""
                Notification.send(event.conn, i.user_id, "inventory.import_done", level="ok",
                                  title="İçe aktarım tamamlandı",
                                  body=f"{i.get('ad')}: {s.get('eklenen', 0)} satır eklendi{ek}.",
                                  link=link, data={"islem_id": i.id})
            else:
                Notification.send(event.conn, i.user_id, "inventory.reindex_done", level="ok",
                                  title="Vektör indeksi yenilendi",
                                  body=f"{s.get('satir', 0)} envanter satırı yeniden indekslendi.",
                                  link=link, data={"islem_id": i.id})
            return
        Notification.send(event.conn, i.user_id, "inventory.failed", level="hata",
                          title=f"{ad} başarısız", body=event.error, link=link, data={"islem_id": i.id})
        AuditLog.record(event.conn, "inventory.failed", actor=User.find(event.conn, i.user_id), target_type="Envanter",
                        target_id=i.id, target_label=f"{ad} (#{i.id})", after={"hata": event.error})
