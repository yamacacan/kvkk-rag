from __future__ import annotations

from pydantic import BaseModel


class DocumentRequest(BaseModel):
    sablon: str
    kurum: str
    adres: str = ""
    web_adres: str = ""
    cagri_merkezi: str = ""
    faaliyet: str = ""            # yalnizca baslik etiketi (Aydinlatma Metni)
    birim: str | None = None      # envanteri bu birime daralt
    faaliyet_filtresi: str | None = None  # envanteri bu faaliyete daralt
    # Veri isleyen protokolu icin
    veri_isleyen: str = ""
    sozlesme_adi: str = ""
    sozlesme_tarihi: str = ""
    protokol_tarihi: str = ""


class ProfileRequest(BaseModel):
    kurum: str = ""
    adres: str = ""
    web_adres: str = ""
    cagri_merkezi: str = ""
    faaliyet: str = ""
    veri_isleyen: str = ""
    sozlesme_adi: str = ""
    sozlesme_tarihi: str = ""
    protokol_tarihi: str = ""
