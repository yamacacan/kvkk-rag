from __future__ import annotations

from pydantic import BaseModel


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


class InventorySearchRequest(BaseModel):
    query: str
    limit: int = 8


class BulkDeleteRequest(BaseModel):
    satir_no: list[int]


class AssignRequest(BaseModel):
    # assigned kapsami: sorumlu (lider denetci) ve ekip uyeleri
    sorumlu_id: int | None = None
    denetciler: list[int] | None = None


class ExportRequest(BaseModel):
    # Kuyruga alinan Excel disa aktarimi: liste filtreleri (+ istege bagli satir secimi)
    birim: str | None = None
    faaliyet: str | None = None
    veri_kategorisi: str | None = None
    hukuki_sebep: str | None = None
    seviye: str | None = None
    sadece_bulgulu: bool = False
    arama: str | None = None
    satir_no: list[int] | None = None
    kurum: str = ""
