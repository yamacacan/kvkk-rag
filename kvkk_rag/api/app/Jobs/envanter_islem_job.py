"""Envanter arka plan isleri (kuyrukta calisir; EnvanterIslemi kaydini gunceller):

  ExportEnvanterJob   : kapsam filtreli envanter -> xlsx dosyasi (istekteki filtrelerle)
  ImportEnvanterJob   : yuklenen xlsx -> envanter satirlari (ekle | degistir)
  ReindexEnvanterJob  : LanceDB vektor indeksini sifirdan kurar

Hepsi ayni iskeleti kullanir (EnvanterIslemJob): kaydi 'calisiyor' yapar, `run()`
calistirir, sonucu yazar, EnvanterIslemiTamamlandi / EnvanterIslemiBasarisiz olayi
atar (bildirim + denetim gunlugu dinleyicilerde). Kapsam istek aninda degil, is
aninda kullanicinin o anki yetkisiyle cozulur."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from ....inventory import store as inv_store
from ...database.connection import connect
from ..Events import EnvanterChanged, EnvanterIslemiBasarisiz, EnvanterIslemiTamamlandi, dispatch
from ..Models import permission_scope as ps
from ..Models.envanter_islemi import HATA, TAMAMLANDI, EnvanterIslemi
from ..Models.user import User
from .base import Job, ShouldQueue

logger = logging.getLogger("kvkk_rag.api.jobs")


class EnvanterIslemJob(Job, ShouldQueue):
    queue = "inventory"
    max_attempts = 1

    def __init__(self, islem_id: int) -> None:
        self.islem_id = islem_id

    def run(self, conn, islem: EnvanterIslemi, user: User) -> None:  # alt siniflar
        raise NotImplementedError

    def handle(self) -> None:
        conn = connect()
        try:
            islem = EnvanterIslemi.find(conn, self.islem_id)
            if islem is None:
                logger.warning("Envanter islemi yok: %s", self.islem_id)
                return
            if islem.durum == TAMAMLANDI:
                return  # ayni is iki kez calisti
            user = User.find(conn, islem.user_id)
            if user is None or not user.active:
                islem.fail(conn, "Kullanıcı bulunamadı veya pasif")
                dispatch(EnvanterIslemiBasarisiz(islem=islem, error="Kullanıcı bulunamadı veya pasif", conn=conn))
                return
            islem.start(conn)
            t0 = time.perf_counter()
            try:
                self.run(conn, islem, user)
            except Exception as e:  # noqa: BLE001 - hata kayda islenir, olay atilir, worker'a da yukselir
                islem.fail(conn, f"{type(e).__name__}: {e}")
                dispatch(EnvanterIslemiBasarisiz(islem=islem, error=str(e), conn=conn))
                raise
            islem.refresh(conn)
            sure = round((time.perf_counter() - t0) * 1000)
            logger.info("Envanter islemi tamamlandi #%s %s (%s ms)", islem.id, islem.tur, sure)
            dispatch(EnvanterIslemiTamamlandi(islem=islem, conn=conn, duration_ms=sure))
        finally:
            conn.close()

    def failed(self, error: Exception) -> None:
        conn = connect()
        try:
            islem = EnvanterIslemi.find(conn, self.islem_id)
            if islem is not None and islem.durum not in (TAMAMLANDI, HATA):
                islem.fail(conn, f"{type(error).__name__}: {error}")
                dispatch(EnvanterIslemiBasarisiz(islem=islem, error=str(error), conn=conn))
        finally:
            conn.close()


class ExportEnvanterJob(EnvanterIslemJob):
    def run(self, conn, islem: EnvanterIslemi, user: User) -> None:
        from ....inventory import excel as inv_excel
        from ..Services.inventory_service import InventoryService

        f = islem.request_data
        rows = InventoryService.rows(conn, user, "inventory", "export")
        secili = InventoryService.filter(rows, f.get("birim"), f.get("faaliyet"), f.get("veri_kategorisi"),
                                         f.get("hukuki_sebep"), f.get("seviye"), bool(f.get("sadece_bulgulu")),
                                         f.get("arama"))
        if f.get("satir_no"):
            istenen = {int(n) for n in f["satir_no"]}
            secili = [r for r in secili if r.satir_no in istenen]
        icerik = inv_excel.build(secili, kurum=f.get("kurum") or "")
        ad = islem.get("ad") or f"veri_envanteri_{time.strftime('%Y%m%d_%H%M')}.xlsx"
        islem.store_output(conn, icerik, ad, sonuc={"satir": len(secili), "toplam": len(rows)})
        dispatch(EnvanterChanged("disa_aktar", conn, user=user, adet=len(secili), etiket=f"{ad} · {len(secili)} satır",
                                 sonra={"adet": len(secili), "islem_id": islem.id,
                                        **{k: v for k, v in f.items() if v not in (None, "", [], False) and k != "kurum"}}))


class ImportEnvanterJob(EnvanterIslemJob):
    """Yuklenen xlsx satirlarini envantere yazar. mod=ekle: mevcutlara ekler; mod=degistir:
    once tum envanteri siler (yalnizca inventory.delete + kapsam all olan kullanici; controller
    dogrular). department kapsamli kullanici yalnizca kendi birimlerinin satirlarini ekleyebilir;
    digerleri atlanir ve sonucta raporlanir."""

    def run(self, conn, islem: EnvanterIslemi, user: User) -> None:
        from ....inventory import loader

        f = islem.request_data
        yol = islem.path
        if yol is None or not yol.exists():
            raise FileNotFoundError("Yüklenen dosya bulunamadı")
        rows, eksik = loader.load(Path(yol))
        eksik = [e for e in eksik if e != "ID"]  # ID sutunu zorunlu degil (satir_no sunucuda uretilir)
        if not rows:
            raise ValueError("Dosyada aktarılacak satır yok")

        kapsam = user.scope_for(conn, "inventory", "create")
        izinli_birimler = set(user.department_names(conn)) if kapsam == ps.DEPARTMENT else None
        if kapsam == ps.NONE:
            raise PermissionError("Envantere kayıt ekleme kapsamınız yok")

        if f.get("mod") == "degistir":
            for r in inv_store.all_rows(conn):
                inv_store.delete(conn, r.satir_no, kullanici_id=user.id)

        eklenen, atlanan = 0, []
        for r in rows:
            veri = {a: getattr(r, a) for a in inv_store.ALANLAR if getattr(r, a, None)}
            if not veri:
                continue
            if izinli_birimler is not None and (veri.get("birim") or "") not in izinli_birimler:
                atlanan.append(r.satir_no)
                continue
            inv_store.create(conn, veri, kaynak="xlsx-yukleme", meta={"created_by": user.id}, kullanici_id=user.id)
            eklenen += 1
        sonuc = {"eklenen": eklenen, "atlanan": len(atlanan), "atlanan_satirlar": atlanan[:50],
                 "eksik_sutunlar": eksik, "mod": f.get("mod", "ekle")}
        islem.finish(conn, sonuc)
        dispatch(EnvanterChanged("ice_aktar", conn, user=user, adet=eklenen,
                                 etiket=f"{islem.get('ad') or 'xlsx'} · {eklenen} satır",
                                 sonra={**sonuc, "islem_id": islem.id}))


class ReindexEnvanterJob(EnvanterIslemJob):
    def run(self, conn, islem: EnvanterIslemi, user: User) -> None:
        from ....inventory import vector as inv_vector  # torch/lancedb: tembel

        rows = inv_store.all_rows(conn)
        n = inv_vector.rebuild(rows)
        islem.finish(conn, {"satir": n, "toplam": inv_vector.count()})
        logger.info("Envanter vektor indeksi yeniden kuruldu: %s satır", n)

