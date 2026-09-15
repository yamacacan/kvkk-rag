from __future__ import annotations

import functools
import io
import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import quote
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from strawberry.fastapi import GraphQLRouter

from ..compliance import generate as comp_generate
from ..compliance import store as comp_store
from ..compliance import profile as comp_profile
from ..compliance import sections as comp_sections
from ..config import settings
from ..graph import query as GQ
from ..graph import schema as GS
from ..index import lexical_store
from ..inventory import audit as inv_audit
from ..inventory import excel as inv_excel
from ..inventory import loader as inv_loader
from ..inventory import store as inv_store
from ..inventory import suggest as inv_suggest
from ..inventory import taxonomy as inv_taxonomy
from ..inventory import vector as inv_vector
from ..chat import engine as chat_engine
from ..llm import prompts
from ..llm.factory import get_llm
from ..retrieval import hybrid
from . import graphql_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kvkk_rag.api")

app = FastAPI(
    title="KVKK-RAG Asistanı API",
    description="6698 Sayılı KVKK Hukuki Uyum ve Akıllı Retrieval API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str
    provider: str | None = None
    limit: int = hybrid.PARENT_LIMIT
    sources_only: bool = False


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "rerank_model": settings.RERANK_MODEL,
        "embed_model": settings.EMBED_MODEL,
        "default_llm": settings.LLM_PROVIDER,
        "authority_weight": hybrid.AUTHORITY_WEIGHT,
    }


@app.post("/api/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    query_text = req.query.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Soru metni boş olamaz.")

    conn = lexical_store.connect()
    try:
        rows = hybrid.search(query_text, conn=conn, limit=req.limit)
    except Exception as e:
        logger.exception("Retrieval hatası")
        raise HTTPException(status_code=500, detail=f"Arama sırasında hata oluştu: {str(e)}")
    finally:
        conn.close()

    sources = []
    for r in rows:
        sources.append({
            "baglayicilik": r.get("baglayicilik"),
            "kaynak_turu": r.get("kaynak_turu"),
            "madde_no": r.get("madde_no"),
            "karar_no": r.get("karar_no"),
            "belge_adi": r.get("belge_adi"),
            "score": round(float(r.get("score", 0)), 4),
            "ce_score": round(float(r.get("ce_score", 0)), 4) if r.get("ce_score") is not None else None,
            "eslesen_parca": r.get("eslesen_parca", ""),
            "text": r.get("text", "")[:1200],
        })

    if req.sources_only:
        return {
            "query": query_text,
            "answer": None,
            "provider": None,
            "sources": sources,
        }

    try:
        llm = get_llm(req.provider)
        messages = prompts.build_messages(query_text, rows)
        answer = llm.complete(messages)
    except Exception as e:
        logger.exception("LLM tamamlama hatası")
        answer = f"⚠️ LLM yanıtı oluşturulurken hata meydana geldi: {str(e)}\n\n(Kaynaklar başarıyla getirildi.)"

    return {
        "query": query_text,
        "answer": answer,
        "provider": getattr(llm, "name", req.provider or "unknown"),
        "sources": sources,
    }


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    provider: str | None = None
    limit: int = hybrid.PARENT_LIMIT


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    # Durum sunucuda tutulmaz; gecmis tarayicidan her turda gelir.
    msgs = [{"role": m.role, "content": m.content} for m in req.messages
            if m.role in ("user", "assistant") and m.content.strip()]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(400, "Son mesaj kullanıcıya ait olmalı.")
    try:
        r = chat_engine.chat(msgs, provider=req.provider, limit=req.limit)
    except Exception as e:
        logger.exception("Sohbet hatası")
        raise HTTPException(500, f"Sohbet sırasında hata: {e}")

    sources = [{
        "baglayicilik": s.get("baglayicilik"), "kaynak_turu": s.get("kaynak_turu"),
        "madde_no": s.get("madde_no"), "karar_no": s.get("karar_no"),
        "belge_adi": s.get("belge_adi"),
        "score": round(float(s.get("score", 0)), 4),
        "eslesen_parca": s.get("eslesen_parca", ""), "text": s.get("text", "")[:1200],
    } for s in r.sources]
    return {
        "answer": r.answer, "provider": r.provider, "sources": sources,
        "analiz": {"bagimsiz_soru": r.analiz.bagimsiz_soru,
                   "envanter_ilgili": r.analiz.envanter_ilgili,
                   "kisisel_veri": r.analiz.kisisel_veri,
                   "birim": r.analiz.birim, "faaliyet": r.analiz.faaliyet},
        "envanter": {
            "eslesen": [{k: v for k, v in e.items() if k != "text"} | {"ozet": e.get("text", "")[:200]}
                        for e in r.envanter_eslesen],
            "oneri": r.oneri,
        },
    }


class InventorySearchRequest(BaseModel):
    query: str
    limit: int = 8


@app.post("/api/inventory/search")
def inventory_search(req: InventorySearchRequest) -> dict[str, Any]:
    # Anlamsal envanter aramasi (vektor). Metin filtresi icin GET /api/inventory?arama=
    if not req.query.strip():
        raise HTTPException(400, "Sorgu boş olamaz")
    return {"sonuclar": inv_vector.search(req.query.strip(), limit=req.limit)}


@app.post("/api/inventory/reindex")
def inventory_reindex() -> dict[str, Any]:
    rows = _inventory()
    return {"indekslenen": inv_vector.rebuild(rows), "toplam": inv_vector.count()}


def _inventory() -> list:
    # Kaynak artik SQLite; ilk caliştirmada xlsx bir kez ice aktarilir.
    conn = inv_store.connect()
    try:
        inv_store.import_xlsx(conn)
        rows = inv_store.all_rows(conn)
    finally:
        conn.close()
    inv_audit.audit(rows)
    return rows


class RowPayload(BaseModel):
    birim: str | None = None
    faaliyet: str | None = None
    veri_kategorisi: str | None = None
    kisisel_veri: str | None = None
    ozel_nitelikli_veri: str | None = None
    kisi_grubu: str | None = None
    isleme_amaci: str | None = None
    hukuki_sebep: str | None = None
    saklama_suresi: str | None = None
    alici_grubu: str | None = None
    yurt_disi_aktarim: str | None = None
    teknik_tedbir: str | None = None
    idari_tedbir: str | None = None
    imha_yontemi: str | None = None
    kayit_ortami: str | None = None
    periyodik_imha_suresi: str | None = None
    yurt_disi_ulke: str | None = None
    aktarim_amaci: str | None = None
    veri_isleyen: str | None = None


class SuggestRequest(BaseModel):
    veri: str
    birim: str | None = None
    faaliyet: str | None = None
    ek_bilgi: str | None = None
    provider: str | None = None


@app.get("/api/taxonomy")
def taxonomy_lists() -> dict[str, Any]:
    # Acilir listeler seeder'lardan; listede yoksa kullanici "Diğer(...)" yazar.
    conn = inv_store.connect()
    try:
        inv_store.import_xlsx(conn)
        mevcut = {alan: inv_store.distinct(conn, alan)
                  for alan in ("birim", "faaliyet", "veri_kategorisi", "kisi_grubu")}
    finally:
        conn.close()
    return {
        "kanonik": {
            "veri_kategorisi": inv_taxonomy.values("veri_kategorisi"),
            "hukuki_sebep": inv_taxonomy.values("hukuki_sebep"),
            "isleme_amaci": inv_taxonomy.values("isleme_amaci"),
            "alici_grubu": inv_taxonomy.values("alici_grubu"),
            "teknik_tedbir": inv_taxonomy.values("teknik_tedbir"),
            "idari_tedbir": inv_taxonomy.values("idari_tedbir"),
        },
        "envanterden": mevcut,
        "ozel_nitelikli_kategoriler": sorted(inv_taxonomy.OZEL_NITELIKLI_KATEGORILER),
        "diger_kalibi": "Diğer(açıklama)",
    }


@app.post("/api/inventory")
def inventory_create(payload: RowPayload) -> dict[str, Any]:
    conn = inv_store.connect()
    try:
        inv_store.import_xlsx(conn)
        satir_no = inv_store.create(conn, payload.model_dump(exclude_none=True))
        row = inv_store.get(conn, satir_no)
    finally:
        conn.close()
    bulgular = inv_audit.audit_row(row)
    return {"satir_no": satir_no, "satir": row.to_dict(),
            "bulgular": [b.to_dict() for b in bulgular]}


@app.patch("/api/inventory/{satir_no}")
def inventory_update(satir_no: int, payload: RowPayload) -> dict[str, Any]:
    conn = inv_store.connect()
    try:
        inv_store.import_xlsx(conn)
        row = inv_store.update(conn, satir_no, payload.model_dump(exclude_none=True))
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, f"Satır {satir_no} bulunamadı")
    bulgular = inv_audit.audit_row(row)
    return {"satir": row.to_dict(), "bulgular": [b.to_dict() for b in bulgular]}


@app.delete("/api/inventory/{satir_no}")
def inventory_delete(satir_no: int) -> dict[str, Any]:
    conn = inv_store.connect()
    try:
        ok = inv_store.delete(conn, satir_no)
    finally:
        conn.close()
    if not ok:
        raise HTTPException(404, f"Satır {satir_no} bulunamadı")
    return {"silindi": satir_no}


@app.post("/api/inventory/suggest")
def inventory_suggest(req: SuggestRequest) -> dict[str, Any]:
    if not req.veri.strip():
        raise HTTPException(400, "Kişisel veri adı boş olamaz")
    conn = inv_store.connect()
    try:
        inv_store.import_xlsx(conn)
        return inv_suggest.suggest(
            req.veri.strip(), req.birim or "", req.faaliyet or "",
            req.ek_bilgi or "", conn_store=conn, provider=req.provider)
    except ValueError as e:
        raise HTTPException(502, f"Öneri üretilemedi: {e}")
    finally:
        conn.close()


class DocumentRequest(BaseModel):
    sablon: str
    kurum: str
    adres: str = ""
    web_adres: str = ""
    faaliyet: str = ""            # yalnizca baslik etiketi (Aydinlatma Metni)
    birim: str | None = None      # envanteri bu birime daralt
    faaliyet_filtresi: str | None = None  # envanteri bu faaliyete daralt
    # Veri isleyen protokolu icin
    veri_isleyen: str = ""
    sozlesme_adi: str = ""
    sozlesme_tarihi: str = ""
    protokol_tarihi: str = ""


def _profil(req: DocumentRequest, rows: list):
    # faaliyet basliktir, filtre degil; kapsam daraltma faaliyet_filtresi ile yapilir
    p = comp_profile.from_inventory(
        rows, kurum=req.kurum, adres=req.adres, web_adres=req.web_adres,
        birim=req.birim, faaliyet=req.faaliyet_filtresi)
    p.faaliyet = req.faaliyet
    p.veri_isleyen = req.veri_isleyen
    p.sozlesme_adi = req.sozlesme_adi
    p.sozlesme_tarihi = req.sozlesme_tarihi
    p.protokol_tarihi = req.protokol_tarihi or f"{date.today():%d.%m.%Y}"
    return p


@functools.lru_cache(maxsize=1)
def _belge_llm():
    # Sablonun yapay zeka ile yazilan bolumleri icin. Saglayici yoksa None
    # doner; sections.py ayni olgulardan deterministik metne duser.
    try:
        return get_llm()
    except Exception as e:
        logger.warning("Belge üretimi LLM'siz çalışacak: %s", e)
        return None


class ProfilePayload(BaseModel):
    kurum: str = ""
    adres: str = ""
    web_adres: str = ""
    faaliyet: str = ""
    veri_isleyen: str = ""
    sozlesme_adi: str = ""
    sozlesme_tarihi: str = ""
    protokol_tarihi: str = ""


@app.get("/api/profile")
def profile_get() -> dict[str, Any]:
    conn = comp_store.connect()
    try:
        return comp_store.get(conn)
    finally:
        conn.close()


@app.put("/api/profile")
def profile_save(payload: ProfilePayload) -> dict[str, Any]:
    if not payload.kurum.strip():
        raise HTTPException(400, "Kurum adı zorunludur")
    conn = comp_store.connect()
    try:
        return comp_store.save(conn, payload.model_dump())
    finally:
        conn.close()


@app.get("/api/documents")
def documents_list() -> dict[str, Any]:
    return {"sablonlar": comp_generate.sablon_bilgisi(),
            "faaliyet_bazli": sorted(comp_generate.FAALIYET_BAZLI)}


@app.get("/api/documents/faaliyetler")
def documents_faaliyetler(birim: str | None = None) -> dict[str, Any]:
    # Aydinlatma metni faaliyet bazlidir; her faaliyetin kendi metni olur.
    rows = _inventory()
    if birim:
        rows = [r for r in rows if r.birim == birim]
    sayac: dict[str, int] = {}
    for r in rows:
        if r.faaliyet:
            sayac[r.faaliyet] = sayac.get(r.faaliyet, 0) + 1
    return {"faaliyetler": [{"ad": k, "satir": v}
                            for k, v in sorted(sayac.items(), key=lambda kv: -kv[1])]}


@app.post("/api/documents/generate-all")
def documents_generate_all(req: DocumentRequest) -> Response:
    # Faaliyet basina bir belge uretip ZIP olarak dondurur.
    if not req.kurum.strip():
        raise HTTPException(400, "Kurum adı zorunludur")
    rows = _inventory()
    if req.birim:
        rows = [r for r in rows if r.birim == req.birim]

    faaliyetler = sorted({r.faaliyet for r in rows if r.faaliyet})
    if not faaliyetler:
        raise HTTPException(400, "Envanterde faaliyet bulunamadı")

    buf = io.BytesIO()
    uretilen, hatalar = 0, []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in faaliyetler:
            alt = [r for r in rows if r.faaliyet == f]
            istek = req.model_copy(update={"faaliyet": f, "faaliyet_filtresi": f})
            try:
                icerik, _, ad, _k = comp_generate.uret(
                    req.sablon, _profil(istek, alt), alt)
            except Exception as e:  # tek faaliyet patlarsa digerleri uretilsin
                hatalar.append(f"{f}: {e}")
                continue
            guvenli = re.sub(r'[\\/:*?"<>|]', "_", f)[:80]
            z.writestr(f"{guvenli}/{ad}", icerik)
            uretilen += 1
        if hatalar:
            z.writestr("HATALAR.txt", "\n".join(hatalar))

    ad = f"{comp_generate.BELGE_ADI[req.sablon].replace(' ', '_')}_tum_faaliyetler.zip"
    return Response(
        content=buf.getvalue(), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{quote(ad)}"',
                 "X-Uretilen-Belge": str(uretilen),
                 "X-Hata-Sayisi": str(len(hatalar))})


@app.post("/api/documents/preview")
def documents_preview(req: DocumentRequest) -> dict[str, Any]:
    # Belgeyi uretmeden once hangi alanlarin bos kalacagini gosterir
    rows = _inventory()
    if req.birim:
        rows = [r for r in rows if r.birim == req.birim]
    if req.faaliyet_filtresi:
        rows = [r for r in rows if r.faaliyet == req.faaliyet_filtresi]
    prof = _profil(req, rows)
    bilgi = {s["anahtar"]: s for s in comp_generate.sablon_bilgisi()}
    s = bilgi.get(req.sablon)
    if not s:
        raise HTTPException(404, f"Şablon bulunamadı: {req.sablon}")
    return {
        "sablon": s["ad"],
        "placeholder": s["placeholder"],
        # kategori/sure/imha ve uretilen bolumler profilden degil envanterden
        # doldugu icin eksik sayilmaz
        "eksik_alanlar": [a for a in prof.eksik_alanlar(s["placeholder"])
                          if a not in comp_generate.TEKRAR_GRUBU
                          and a not in comp_generate.URETILEN_PH],
        "uretilen_bolumler": [
            {"alan": a,
             "kaynak": "yapay_zeka" if a in comp_sections.YAPAY_ZEKA else "veritabani"}
            for a in s.get("uretilen_bolumler", [])],
        "envanter_satiri": len(rows),
        "profil": {
            "isleme_amaci": len(prof.isleme_amaclari),
            "hukuki_sebep": len(prof.hukuki_sebepler),
            "veri_kategorisi": len(prof.veri_kategorileri),
            "kisi_grubu": len(prof.kisi_gruplari),
            "teknik_tedbir": len(prof.teknik_tedbirler),
            "idari_tedbir": len(prof.idari_tedbirler),
        },
    }


@app.post("/api/documents/generate")
def documents_generate(req: DocumentRequest) -> Response:
    if not req.kurum.strip():
        raise HTTPException(400, "Kurum adı zorunludur")
    rows = _inventory()
    if req.birim:
        rows = [r for r in rows if r.birim == req.birim]
    if req.faaliyet_filtresi:
        rows = [r for r in rows if r.faaliyet == req.faaliyet_filtresi]
    try:
        icerik, kalan, ad, kaynak = comp_generate.uret(
            req.sablon, _profil(req, rows), rows, _belge_llm())
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, str(e))

    basliklar = {"Content-Disposition": f'attachment; filename="{quote(ad)}"'}
    if kalan:
        basliklar["X-Doldurulmayan-Alanlar"] = ",".join(kalan)
    ai = [k for k, v in kaynak.items() if v == "yapay_zeka"]
    if ai:
        # Yapay zeka ile yazilan bolumler: kullanici hangilerini gozden
        # gecirecegini bilmeli
        basliklar["X-Yapay-Zeka-Bolumleri"] = ",".join(sorted(ai))
    return Response(
        content=icerik,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=basliklar)


class BulkDeleteRequest(BaseModel):
    satir_no: list[int]


@app.post("/api/inventory/bulk-delete")
def inventory_bulk_delete(req: BulkDeleteRequest) -> dict[str, Any]:
    if not req.satir_no:
        raise HTTPException(400, "Silinecek satır seçilmedi")
    conn = inv_store.connect()
    try:
        silinen = [n for n in req.satir_no if inv_store.delete(conn, n)]
    finally:
        conn.close()
    return {"silinen": silinen, "adet": len(silinen),
            "bulunamayan": sorted(set(req.satir_no) - set(silinen))}


@app.get("/api/inventory/export")
def inventory_export(
    birim: str | None = None,
    faaliyet: str | None = None,
    veri_kategorisi: str | None = None,
    seviye: str | None = None,
    sadece_bulgulu: bool = False,
    arama: str | None = None,
    kurum: str = "",
) -> Response:
    rows = _inventory()

    def ok(r) -> bool:
        for deger, alan in ((birim, r.birim), (faaliyet, r.faaliyet),
                            (veri_kategorisi, r.veri_kategorisi)):
            if deger and deger.lower() not in (alan or "").lower():
                return False
        if sadece_bulgulu and not r.bulgular:
            return False
        if seviye and not any(b["seviye"] == seviye for b in r.bulgular):
            return False
        if arama:
            hay = " ".join(str(v or "") for v in r.to_dict().values()).lower()
            if arama.lower() not in hay:
                return False
        return True

    secili = [r for r in rows if ok(r)]
    icerik = inv_excel.build(secili, kurum=kurum)
    ad = f"veri_envanteri_{date.today():%Y%m%d}.xlsx"
    return Response(
        content=icerik,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{ad}"'})


@app.get("/api/inventory/{satir_no}/history")
def inventory_history(satir_no: int) -> dict[str, Any]:
    conn = inv_store.connect()
    try:
        return {"kayitlar": inv_store.history(conn, satir_no)}
    finally:
        conn.close()


@app.get("/api/inventory")
def inventory(
    birim: str | None = None,
    faaliyet: str | None = None,
    veri_kategorisi: str | None = None,
    hukuki_sebep: str | None = None,
    seviye: str | None = None,
    sadece_bulgulu: bool = False,
    arama: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _inventory()
    AGIRLIK = {"kritik": 10, "yuksek": 5, "orta": 2, "dusuk": 1}

    def ok(r) -> bool:
        for deger, alan in ((birim, r.birim), (faaliyet, r.faaliyet),
                            (veri_kategorisi, r.veri_kategorisi),
                            (hukuki_sebep, r.hukuki_sebep)):
            if deger and deger.lower() not in (alan or "").lower():
                return False
        if sadece_bulgulu and not r.bulgular:
            return False
        if seviye and not any(b["seviye"] == seviye for b in r.bulgular):
            return False
        if arama:
            hay = " ".join(str(v or "") for v in r.to_dict().values()).lower()
            if arama.lower() not in hay:
                return False
        return True

    filtered = [r for r in rows if ok(r)]
    sayfa = filtered[offset: offset + limit]
    return {
        "toplam": len(rows),
        "filtrelenmis": len(filtered),
        "offset": offset,
        "limit": limit,
        "satirlar": [
            {**r.to_dict(),
             "risk_skoru": sum(AGIRLIK.get(b["seviye"], 0) for b in r.bulgular)}
            for r in sayfa
        ],
    }


@app.get("/api/inventory/summary")
def inventory_summary() -> dict[str, Any]:
    rows = _inventory()
    sev: dict[str, int] = {}
    kod: dict[str, int] = {}
    for r in rows:
        for b in r.bulgular:
            sev[b["seviye"]] = sev.get(b["seviye"], 0) + 1
            kod[b["kod"]] = kod.get(b["kod"], 0) + 1
    temiz = sum(1 for r in rows if not r.bulgular)

    def dagilim(alan: str, n: int = 12) -> list[dict[str, Any]]:
        c: dict[str, int] = {}
        for r in rows:
            v = getattr(r, alan)
            if v:
                c[v] = c.get(v, 0) + 1
        return [{"deger": k, "adet": v}
                for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:n]]

    return {
        "satir": len(rows), "bulgu": sum(len(r.bulgular) for r in rows),
        "temiz_satir": temiz,
        "uyum_orani": round(temiz / len(rows), 4) if rows else 0.0,
        "seviye": sev, "kod": kod,
        "birim": dagilim("birim"), "faaliyet": dagilim("faaliyet"),
        "veri_kategorisi": dagilim("veri_kategorisi", 20),
    }


@app.get("/api/inventory/{satir_no}")
def inventory_get(satir_no: int) -> dict[str, Any]:
    # summary/export gibi sabit yollardan SONRA tanimli olmali; aksi halde int
    # dogrulamasi onlari 422 ile yutar.
    conn = inv_store.connect()
    try:
        row = inv_store.get(conn, satir_no)
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, f"Satır {satir_no} bulunamadı")
    row.bulgular = [b.to_dict() for b in inv_audit.audit_row(row)]
    return {"satir": row.to_dict()}


@app.get("/api/graph/risk")
def graph_risk(limit: int = 10) -> dict[str, Any]:
    conn = GS.connect()
    try:
        return {"faaliyetler": GQ.faaliyet_riski(conn, limit),
                "graf": GS.stats(conn)}
    finally:
        conn.close()


@app.get("/api/graph/madde/{madde_no}")
def graph_madde(madde_no: str) -> dict[str, Any]:
    conn = GS.connect()
    try:
        out = GQ.madde_etkisi(conn, madde_no)
        if not out:
            raise HTTPException(404, f"KVKK m.{madde_no} grafta bulunamadı")
        return out
    finally:
        conn.close()


app.include_router(GraphQLRouter(graphql_schema.schema), prefix="/graphql")

# Web arayuzu (varsa) kokten servis edilir
web_dir = Path("/app/web")
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
