"""ASGI giris noktasi: uvicorn kvkk_rag.api.server:app

Uclar app/Http/Controller altinda (MVC); kimlik ve yetki app/Http/Middleware;
kapsam katmani app/Services. Uygulama bootstrap.create_app() ile kurulur."""
from __future__ import annotations

import logging

from .bootstrap import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()
