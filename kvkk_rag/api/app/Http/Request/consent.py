"""Acik riza kaydi istek semalari. Hata mesajlari Turkce (422)."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from ...Models.consent import DURUMLAR, GERI_CEKILDI, YONTEMLER, tc_gecerli


class ConsentRequest(BaseModel):
    faaliyet: str = Field(min_length=1, max_length=300)
    tc_kimlik: str = Field(min_length=11, max_length=11)
    ad: str = Field(min_length=1, max_length=120)
    soyad: str = Field(min_length=1, max_length=120)
    durum: str
    onay_tarihi: str | None = None          # ISO 8601 (arayuz datetime-local)
    geri_cekme_tarihi: str | None = None
    onay_yontemi: str | None = None
    notlar: str | None = Field(default=None, max_length=2000)

    @field_validator("tc_kimlik")
    @classmethod
    def _tc(cls, v: str) -> str:
        v = (v or "").strip()
        if not tc_gecerli(v):
            raise ValueError("Geçerli bir T.C. Kimlik Numarası giriniz (11 hane).")
        return v

    @field_validator("ad", "soyad", "faaliyet")
    @classmethod
    def _bosluk(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Bu alan zorunludur.")
        return v

    @field_validator("durum")
    @classmethod
    def _durum(cls, v: str) -> str:
        if v not in DURUMLAR:
            raise ValueError("Onay durumu Onaylandı, Onaylanmadı veya Geri Çekildi olmalıdır.")
        return v

    @field_validator("onay_yontemi")
    @classmethod
    def _yontem(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if v not in YONTEMLER:
            raise ValueError("Geçersiz onay yöntemi.")
        return v

    @model_validator(mode="after")
    def _geri_cekme(self):
        if self.durum == GERI_CEKILDI and not (self.geri_cekme_tarihi or "").strip():
            raise ValueError("Geri çekilen rıza için geri çekme tarihi zorunludur.")
        if self.durum != GERI_CEKILDI:
            self.geri_cekme_tarihi = None
        return self
