"""Envanter uclari. Iki kademe burada bulusur:
  1. `permission="inventory.view"`  -> kullanici bu eylemi yapabilir mi? (Spatie)
  2. ScopeFilter.apply / authorize  -> hangi veriler uzerinde? (kapsam)

Agir isler kuyrukta: POST /export (Excel), POST /import (Excel'den), POST /reindex
bir `envanter_islemleri` kaydi acip isi kuyruga yazar (202); bitince bildirim gelir,
cikti GET /islemler/{id}/indir ile alinir. GET /export es zamanli indirme olarak kalir.

Sabit yollar (summary, export, islemler...) {satir_no} yollarindan ONCE tanimlidir;
aksi halde int dogrulamasi onlari 422 ile yutar."""
from __future__ import annotations

import re
import sqlite3
from datetime import date
from typing import Any
from urllib.parse import quote

from fastapi import Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from ....database.connection import get_db
from ....resource import EnvanterResource
from ...Events import EnvanterChanged, dispatch
from ...Exports.envanter_export import EnvanterExport
from ...Jobs.envanter_islem_job import ExportEnvanterJob, ImportEnvanterJob, ReindexEnvanterJob
from ...Models import permission_scope as ps
from ...Models.envanter_islemi import (DISA_AKTAR, ICE_AKTAR, XLSX, YENIDEN_INDEKSLE, EnvanterIslemi,
                                       islem_dizini)
from ...Models.user import User
from ...Services.inventory_service import InventoryService
from ..Middleware.authenticate import authenticate
from ..Request.inventory import (AssignRequest, BulkDeleteRequest, ExportRequest, InventorySearchRequest,
                                 RowPayload, SuggestRequest)
from .base import Controller, route

MODULE = "inventory"
YUKLEME_SINIRI = 20 * 1024 * 1024  # 20 MB


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    return ileri.split(",")[0].strip() if ileri else (request.client.host if request.client else None)


class InventoryController(Controller):
    prefix = "/api/inventory"
    tags = ["envanter"]
    middleware = (authenticate,)

    # ---- listeleme / ozet / disa aktarim (kapsam: sorgu seviyesi) ----
    @route("GET", "", permission="inventory.view")
    def index(self, birim: str | None = None, faaliyet: str | None = None,
              veri_kategorisi: str | None = None, hukuki_sebep: str | None = None,
              seviye: str | None = None, sadece_bulgulu: bool = False,
              arama: str | None = None, limit: int = 50, offset: int = 0,
              user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        rows = InventoryService.rows(conn, user, MODULE, "view")
        filtered = InventoryService.filter(rows, birim, faaliyet, veri_kategorisi,
                                           hukuki_sebep, seviye, sadece_bulgulu, arama)
        return {
            "toplam": len(rows), "filtrelenmis": len(filtered),
            "offset": offset, "limit": limit,
            "kapsam": user.scope_for(conn, MODULE, "view"),
            "satirlar": EnvanterResource.collection(filtered[offset: offset + limit]),
        }

    @route("GET", "/summary", permission="findings.view")
    def summary(self, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Bulgu panosu: kullanicinin findings.view kapsamindaki satirlar uzerinden
        rows = InventoryService.rows(conn, user, "findings", "view")
        return {**InventoryService.summary(rows), "kapsam": user.scope_for(conn, "findings", "view")}

    @route("GET", "/export", permission="inventory.export")
    def export(self, request: Request, birim: str | None = None, faaliyet: str | None = None,
               veri_kategorisi: str | None = None, seviye: str | None = None,
               sadece_bulgulu: bool = False, arama: str | None = None, kurum: str = "",
               user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> Response:
        rows = InventoryService.rows(conn, user, MODULE, "export")
        secili = InventoryService.filter(rows, birim, faaliyet, veri_kategorisi,
                                         seviye=seviye, sadece_bulgulu=sadece_bulgulu, arama=arama)
        ad = f"veri_envanteri_{date.today():%Y%m%d}.xlsx"
        # Disa aktarim da bir veri aktarimidir: denetim gunlugune
        dispatch(EnvanterChanged("disa_aktar", conn, user=user, adet=len(secili), etiket=f"{ad} · {len(secili)} satır",
                                 sonra={"adet": len(secili), "birim": birim, "faaliyet": faaliyet,
                                        "veri_kategorisi": veri_kategorisi, "seviye": seviye, "arama": arama},
                                 ip=_ip(request)))
        return EnvanterExport(secili, kurum=kurum).download(ad)

    # ---- kuyruklu isler: disa aktarim / ice aktarim / yeniden indeksleme ----
    def _kuyruga_al(self, conn: sqlite3.Connection, user: User, job_cls, tur: str, istek: dict[str, Any],
                    **alanlar: Any) -> dict[str, Any]:
        islem = EnvanterIslemi.open(conn, user.id, tur, istek, **alanlar)
        job = job_cls(islem.id).dispatch(conn=conn, user_id=user.id)
        islem.update(conn, job_id=job.id)
        return {"islem": islem.to_dict(), "job_id": job.id, "kuyrukta": True}

    @route("POST", "/export", permission="inventory.export", status_code=202)
    def export_queued(self, req: ExportRequest, user: User = Depends(authenticate),
                      conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Excel arka planda uretilir; hazir olunca bildirim, /islemler/{id}/indir ile indirme
        ad = f"veri_envanteri_{date.today():%Y%m%d}.xlsx"
        return self._kuyruga_al(conn, user, ExportEnvanterJob, DISA_AKTAR, req.model_dump(), ad=ad)

    @route("POST", "/import", permission="inventory.create", status_code=202)
    async def import_queued(self, dosya: UploadFile = File(...), mod: str = Form("ekle"),
                            user: User = Depends(authenticate),
                            conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # xlsx yuklenir, diske yazilir, satirlar kuyrukta eklenir. mod=degistir tum envanteri
        # siler: yalnizca inventory.delete izni + 'all' kapsami olan kullanici.
        if mod not in ("ekle", "degistir"):
            raise HTTPException(422, "mod 'ekle' veya 'degistir' olmalı")
        if mod == "degistir" and not (user.can(conn, "inventory.delete")
                                      and user.scope_for(conn, MODULE, "delete") == ps.ALL):
            raise HTTPException(403, "Envanteri değiştirmek (tümünü silip yeniden yüklemek) için tam kapsamlı silme yetkisi gerekir.")
        if user.scope_for(conn, MODULE, "create") == ps.NONE:
            raise HTTPException(403, "Envantere kayıt ekleme kapsamınız yok.")
        ad = (dosya.filename or "envanter.xlsx").rsplit("/", 1)[-1]
        if not ad.lower().endswith(".xlsx"):
            raise HTTPException(422, "Yalnızca .xlsx dosyası yüklenebilir")
        icerik = await dosya.read()
        if not icerik:
            raise HTTPException(422, "Dosya boş")
        if len(icerik) > YUKLEME_SINIRI:
            raise HTTPException(413, "Dosya 20 MB sınırını aşıyor")
        guvenli = re.sub(r'[^\w.\-]+', "_", ad)[:120]
        islem = EnvanterIslemi.open(conn, user.id, ICE_AKTAR, {"mod": mod, "dosya_adi": ad}, ad=ad, boyut=len(icerik))
        yol = islem_dizini() / f"yukleme_{islem.id}_{guvenli}"
        yol.write_bytes(icerik)
        islem.update(conn, dosya=str(yol))
        job = ImportEnvanterJob(islem.id).dispatch(conn=conn, user_id=user.id)
        islem.update(conn, job_id=job.id)
        return {"islem": islem.to_dict(), "job_id": job.id, "kuyrukta": True}

    @route("GET", "/islemler", permission="inventory.view")
    def islemler(self, limit: int = 30, user: User = Depends(authenticate),
                 conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"islemler": [i.to_dict() for i in EnvanterIslemi.for_user(conn, user.id, min(limit, 100))],
                "bekleyen": EnvanterIslemi.pending_count(conn, user.id)}

    def _islemim(self, conn: sqlite3.Connection, user: User, islem_id: int) -> EnvanterIslemi:
        islem = self.find_or_fail(EnvanterIslemi.find(conn, islem_id), "İşlem bulunamadı")
        if islem.user_id != user.id and not user.is_super(conn):
            raise HTTPException(403, "Bu işlem size ait değil.")
        return islem

    @route("GET", "/islemler/{islem_id}", permission="inventory.view")
    def islem(self, islem_id: int, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"islem": self._islemim(conn, user, islem_id).to_dict()}

    @route("GET", "/islemler/{islem_id}/indir", permission="inventory.export")
    def islem_indir(self, islem_id: int, user: User = Depends(authenticate),
                    conn: sqlite3.Connection = Depends(get_db)) -> Response:
        islem = self._islemim(conn, user, islem_id)
        if not islem.downloadable:
            raise HTTPException(409, "Dosya henüz hazır değil." if islem.durum != "hata" else f"İşlem başarısız: {islem.hata}")
        return FileResponse(str(islem.path), media_type=XLSX, filename=islem.ad,
                            headers={"Content-Disposition": f'attachment; filename="{quote(islem.ad)}"'})

    @route("DELETE", "/islemler/{islem_id}", permission="inventory.view")
    def islem_sil(self, islem_id: int, user: User = Depends(authenticate),
                  conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        islem = self._islemim(conn, user, islem_id)
        if islem.durum in ("kuyrukta", "calisiyor"):
            raise HTTPException(409, "Süren işlem silinemez; bitmesini bekleyin.")
        islem.delete(conn)
        return {"silindi": islem_id}

    # ---- anlamsal arama / yeniden indeksleme ----
    @route("POST", "/search", permission="inventory.search")
    def search(self, req: InventorySearchRequest, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Vektor indeksi SQL disi; kapsam, gorunur satir_no kumesi LanceDB on-filtresi olarak verilir
        if not req.query.strip():
            raise HTTPException(400, "Sorgu boş olamaz")
        from .....inventory import vector as inv_vector
        gorunur = InventoryService.visible_ids(conn, user, MODULE, "search")
        if gorunur is not None and not gorunur:
            return {"sonuclar": []}
        where = None if gorunur is None else f"satir_no IN ({', '.join(str(int(n)) for n in gorunur)})"
        return {"sonuclar": inv_vector.search(req.query.strip(), limit=req.limit, where=where)}

    @route("POST", "/reindex", permission="inventory.reindex", status_code=202)
    def reindex(self, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        InventoryService.ensure_imported(conn, user)
        dispatch(EnvanterChanged("yeniden_indeksle", conn, user=user, etiket="vektör indeksi", ip=_ip(request)))
        return {**self._kuyruga_al(conn, user, ReindexEnvanterJob, YENIDEN_INDEKSLE, {}), "kuyruga_alindi": True}

    # ---- olusturma ----
    @route("POST", "", permission="inventory.create")
    def store(self, payload: RowPayload, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        self.authorize(conn, user, MODULE, "create")
        veri = payload.model_dump(exclude_none=True)
        # department kapsaminda yalnizca kendi departmanina kayit acabilir
        if user.scope_for(conn, MODULE, "create") == ps.DEPARTMENT:
            if (veri.get("birim") or "") not in user.department_names(conn):
                raise HTTPException(403, "Yalnızca kendi departmanınız için kayıt oluşturabilirsiniz.")
        satir_no, row = InventoryService.create(conn, user, veri, ip=_ip(request))
        return {"satir_no": satir_no, "satir": row.to_dict(),
                "bulgular": InventoryService.audit_row(row)}

    @route("POST", "/suggest", permission="inventory.suggest")
    def suggest(self, req: SuggestRequest, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if not req.veri.strip():
            raise HTTPException(400, "Kişisel veri adı boş olamaz")
        from .....inventory import suggest as inv_suggest
        InventoryService.ensure_imported(conn)
        try:
            return inv_suggest.suggest(
                req.veri.strip(), req.birim or "", req.faaliyet or "",
                req.ek_bilgi or "", conn_store=conn, provider=req.provider)
        except ValueError as e:
            raise HTTPException(502, f"Öneri üretilemedi: {e}")

    @route("POST", "/bulk-delete", permission="inventory.delete")
    def bulk_delete(self, req: BulkDeleteRequest, request: Request, user: User = Depends(authenticate),
                    conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if not req.satir_no:
            raise HTTPException(400, "Silinecek satır seçilmedi")
        silinen, yetkisiz = [], []
        for n in req.satir_no:
            kayit = InventoryService.find(conn, n)
            if not kayit:
                continue
            if not user.has_scoped_permission(conn, MODULE, "delete", kayit):
                yetkisiz.append(n)
                continue
            if InventoryService.delete(conn, user, n, ip=_ip(request)):
                silinen.append(n)
        return {"silinen": silinen, "adet": len(silinen), "yetkisiz": yetkisiz,
                "bulunamayan": sorted(set(req.satir_no) - set(silinen) - set(yetkisiz))}

    # ---- tekil kayit (kapsam: kayit seviyesi) ----
    @route("GET", "/{satir_no}/history", permission="inventory.history")
    def history(self, satir_no: int, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        kayit = self.find_or_fail(InventoryService.find(conn, satir_no), f"Satır {satir_no} bulunamadı")
        self.authorize(conn, user, MODULE, "history", kayit)
        return {"kayitlar": InventoryService.history(conn, satir_no)}

    @route("POST", "/{satir_no}/assign", permission="inventory.assign")
    def assign(self, satir_no: int, req: AssignRequest, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        kayit = self.find_or_fail(InventoryService.find(conn, satir_no), f"Satır {satir_no} bulunamadı")
        self.authorize(conn, user, MODULE, "assign", kayit)
        for uid in [req.sorumlu_id, *(req.denetciler or [])]:
            if uid is not None and User.find(conn, uid) is None:
                raise HTTPException(422, f"Kullanıcı bulunamadı: {uid}")
        once = {"sorumlu_id": kayit.get("sorumlu_id"), "denetciler": kayit.denetci_ids(conn)}
        kayit.assign(conn, req.sorumlu_id, req.denetciler)
        dispatch(EnvanterChanged("ata", conn, user=user, satir_no=satir_no, once=once,
                                 sonra={"sorumlu_id": kayit.get("sorumlu_id"), "denetciler": kayit.denetci_ids(conn)},
                                 ip=_ip(request)))
        return {"satir_no": satir_no, "sorumlu_id": kayit.get("sorumlu_id"),
                "denetciler": kayit.denetci_ids(conn)}

    @route("GET", "/{satir_no}", permission="inventory.view")
    def show(self, satir_no: int, user: User = Depends(authenticate),
             conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        kayit = self.find_or_fail(InventoryService.find(conn, satir_no), f"Satır {satir_no} bulunamadı")
        self.authorize(conn, user, MODULE, "view", kayit)
        row = kayit.to_inventory_row()
        row.bulgular = InventoryService.audit_row(row)
        return {"satir": row.to_dict(),
                "sahiplik": {"created_by": kayit.get("created_by"),
                             "sorumlu_id": kayit.get("sorumlu_id"),
                             "denetciler": kayit.denetci_ids(conn)}}

    @route("PATCH", "/{satir_no}", permission="inventory.update")
    def update(self, satir_no: int, payload: RowPayload, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        kayit = self.find_or_fail(InventoryService.find(conn, satir_no), f"Satır {satir_no} bulunamadı")
        self.authorize(conn, user, MODULE, "update", kayit)
        row = InventoryService.update(conn, user, satir_no, payload.model_dump(exclude_none=True), ip=_ip(request))
        return {"satir": row.to_dict(), "bulgular": InventoryService.audit_row(row)}

    @route("DELETE", "/{satir_no}", permission="inventory.delete")
    def destroy(self, satir_no: int, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        kayit = self.find_or_fail(InventoryService.find(conn, satir_no), f"Satır {satir_no} bulunamadı")
        self.authorize(conn, user, MODULE, "delete", kayit)
        InventoryService.delete(conn, user, satir_no, ip=_ip(request))
        return {"silindi": satir_no}
