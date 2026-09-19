from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def register(app: FastAPI) -> None:
    kokenler = [k.strip() for k in os.getenv("KVKK_CORS_ORIGINS", "*").split(",") if k.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=kokenler,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition", "X-Uretilen-Belge", "X-Hata-Sayisi",
                        "X-Doldurulmayan-Alanlar", "X-Yapay-Zeka-Bolumleri"],
    )
