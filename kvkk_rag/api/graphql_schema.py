# GraphQL semasi: envanter, bulgular, graf ve mevzuat aramasi tek arabirimde.
from __future__ import annotations

import functools
from typing import Any

import strawberry

from ..graph import query as GQ
from ..graph import schema as GS
from ..index import lexical_store
from ..inventory import audit as inv_audit
from ..inventory import loader as inv_loader
from ..retrieval import hybrid


@functools.lru_cache(maxsize=1)
def _inventory() -> list[inv_loader.InventoryRow]:
    rows, _ = inv_loader.load()
    inv_audit.audit(rows)
    return rows


@strawberry.type
class Bulgu:
    kod: str
    seviye: str
    baslik: str
    aciklama: str
    dayanak: str
    alan: str | None
    satir_no: int


@strawberry.type
class EnvanterSatiri:
    satir_no: int
    birim: str | None
    faaliyet: str | None
    veri_kategorisi: str | None
    kisisel_veri: str | None
    ozel_nitelikli_veri: str | None
    kisi_grubu: str | None
    isleme_amaci: str | None
    hukuki_sebep: str | None
    saklama_suresi: str | None
    alici_grubu: str | None
    yurt_disi_aktarim: str | None
    teknik_tedbir: str | None
    idari_tedbir: str | None
    imha_yontemi: str | None
    bulgular: list[Bulgu]

    @strawberry.field
    def risk_skoru(self) -> int:
        agirlik = {"kritik": 10, "yuksek": 5, "orta": 2, "dusuk": 1}
        return sum(agirlik.get(b.seviye, 0) for b in self.bulgular)


@strawberry.type
class DenetimOzeti:
    satir: int
    bulgu: int
    temiz_satir: int
    uyum_orani: float
    kritik: int
    yuksek: int
    orta: int


@strawberry.type
class FaaliyetRisk:
    faaliyet: str
    satir: int
    bulgu: int
    kritik: int


@strawberry.type
class Kaynak:
    baglayicilik: str
    kaynak_turu: str
    belge_adi: str
    madde_no: str | None
    karar_no: str | None
    skor: float
    metin: str


@strawberry.type
class MaddeEtkisi:
    madde_no: str
    baslik: str | None
    atif_yapan_karar: int
    hukuki_sebepler: list[str]


def _to_bulgu(b: dict, satir_no: int) -> Bulgu:
    return Bulgu(kod=b["kod"], seviye=b["seviye"], baslik=b["baslik"],
                 aciklama=b["aciklama"], dayanak=b["dayanak"],
                 alan=b.get("alan"), satir_no=satir_no)


def _to_row(r: inv_loader.InventoryRow) -> EnvanterSatiri:
    return EnvanterSatiri(
        satir_no=r.satir_no, birim=r.birim, faaliyet=r.faaliyet,
        veri_kategorisi=r.veri_kategorisi, kisisel_veri=r.kisisel_veri,
        ozel_nitelikli_veri=r.ozel_nitelikli_veri, kisi_grubu=r.kisi_grubu,
        isleme_amaci=r.isleme_amaci, hukuki_sebep=r.hukuki_sebep,
        saklama_suresi=r.saklama_suresi, alici_grubu=r.alici_grubu,
        yurt_disi_aktarim=r.yurt_disi_aktarim, teknik_tedbir=r.teknik_tedbir,
        idari_tedbir=r.idari_tedbir, imha_yontemi=r.imha_yontemi,
        bulgular=[_to_bulgu(b, r.satir_no) for b in r.bulgular])


@strawberry.type
class Query:
    @strawberry.field(description="Envanter satirlari; her alanda bagimsiz filtre")
    def envanter(
        self,
        birim: str | None = None,
        faaliyet: str | None = None,
        veri_kategorisi: str | None = None,
        hukuki_sebep: str | None = None,
        sadece_bulgulu: bool = False,
        seviye: str | None = None,
        arama: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EnvanterSatiri]:
        rows = _inventory()

        def ok(r: inv_loader.InventoryRow) -> bool:
            if birim and birim.lower() not in (r.birim or "").lower():
                return False
            if faaliyet and faaliyet.lower() not in (r.faaliyet or "").lower():
                return False
            if veri_kategorisi and veri_kategorisi.lower() not in (r.veri_kategorisi or "").lower():
                return False
            if hukuki_sebep and hukuki_sebep.lower() not in (r.hukuki_sebep or "").lower():
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

        return [_to_row(r) for r in rows if ok(r)][offset: offset + limit]

    @strawberry.field(description="Envanter denetim ozeti")
    def denetim_ozeti(self) -> DenetimOzeti:
        rows = _inventory()
        bulgu = sum(len(r.bulgular) for r in rows)
        temiz = sum(1 for r in rows if not r.bulgular)
        sev: dict[str, int] = {}
        for r in rows:
            for b in r.bulgular:
                sev[b["seviye"]] = sev.get(b["seviye"], 0) + 1
        return DenetimOzeti(
            satir=len(rows), bulgu=bulgu, temiz_satir=temiz,
            uyum_orani=round(temiz / len(rows), 4) if rows else 0.0,
            kritik=sev.get("kritik", 0), yuksek=sev.get("yuksek", 0),
            orta=sev.get("orta", 0))

    @strawberry.field(description="Bulgu sayisina gore en riskli faaliyetler")
    def faaliyet_riski(self, limit: int = 10) -> list[FaaliyetRisk]:
        conn = GS.connect()
        try:
            return [FaaliyetRisk(faaliyet=r["faaliyet"], satir=r["satir"],
                                 bulgu=r["bulgu"] or 0, kritik=r["kritik"] or 0)
                    for r in GQ.faaliyet_riski(conn, limit)]
        finally:
            conn.close()

    @strawberry.field(description="Mevzuatta kaynak dayanakli arama")
    def mevzuat_ara(self, soru: str, limit: int = 8) -> list[Kaynak]:
        conn = lexical_store.connect()
        try:
            rows = hybrid.search(soru, conn=conn, limit=limit)
        finally:
            conn.close()
        return [Kaynak(baglayicilik=r["baglayicilik"], kaynak_turu=r["kaynak_turu"],
                       belge_adi=r["belge_adi"], madde_no=r["madde_no"],
                       karar_no=r["karar_no"], skor=round(float(r["score"]), 4),
                       metin=(r["text_raw"] or "")[:1200])
                for r in rows]

    @strawberry.field(description="Bir KVKK maddesine bagli kararlar ve hukuki sebepler")
    def madde_etkisi(self, madde_no: str) -> MaddeEtkisi | None:
        conn = GS.connect()
        try:
            m = GQ.madde_etkisi(conn, madde_no)
            if not m:
                return None
            return MaddeEtkisi(
                madde_no=madde_no, baslik=m["madde"]["props"].get("baslik"),
                atif_yapan_karar=m["atif_yapan_karar"],
                hukuki_sebepler=m["hukuki_sebepler"])
        finally:
            conn.close()

    @strawberry.field(description="Graf istatistikleri")
    def graf_ozeti(self) -> strawberry.scalars.JSON:
        conn = GS.connect()
        try:
            return GS.stats(conn)
        finally:
            conn.close()


schema = strawberry.Schema(query=Query)
