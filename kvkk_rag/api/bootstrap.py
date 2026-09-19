"""Uygulama fabrikasi (Laravel bootstrap/app.php).

create_app(): gozlemci/dinleyici kaydi, CORS, istisna isleyicileri, controller
rotalari, GraphQL, Vue arayuzu (web/dist, SPA geri donusu). Baslangicta gocler
uygulanir ve eksik rol/izin/kapsam/departman tohumlanir (mevcut roller
degistirilmez; tam esitleme icin `db:seed --sync`)."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable

from fastapi import Depends, FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from .app import boot
from .app.Exceptions.handler import register as register_exceptions
from .app.Http.Controller import CONTROLLERS
from .app.Http.Middleware.authenticate import authenticate
from .app.Http.Middleware.cors import register as register_cors
from .app.Services.queue import Worker
from .database.connection import connect
from .database.seeders import DatabaseSeeder

logger = logging.getLogger("kvkk_rag.api")

# Vue derlemesi (vite build -> web/dist); yoksa eski statik arayuz klasoru
WEB_ROOT = Path(os.getenv("KVKK_WEB_DIR", "/app/web"))
WEB_DIST = WEB_ROOT / "dist"


class SpaStaticFiles(StaticFiles):
    """Vue Router history modu: dosya yoksa index.html doner. Bilinmeyen /api ve
    /graphql yollari ile uzantili dosya istekleri 404 kalir."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            api_yolu = path.startswith(("api/", "graphql")) or path in ("api", "graphql")
            if e.status_code == 404 and not api_yolu and "." not in path.rsplit("/", 1)[-1]:
                return await super().get_response("index.html", scope)
            raise


def migrate_and_seed(with_admin: bool = True) -> None:
    conn = connect()  # gocler connect() icinde uygulanir
    try:
        sonuc = DatabaseSeeder.run(conn, with_admin=with_admin)
    finally:
        conn.close()
    logger.info("RBAC tohumlama: %s", {k: v for k, v in sonuc.items() if k != "admin"})


def create_app(controllers: Iterable[type] | None = None, graphql: bool = True,
               static: bool = True, seed: bool = True, worker: bool = True) -> FastAPI:
    boot()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if seed:
            migrate_and_seed()
        # Kuyruk worker'i ayni surecte (KVKK_QUEUE_WORKER=0 ile kapatilip `queue:work` ayrica calistirilabilir)
        if worker:
            Worker.start_thread()
        yield
        if worker:
            Worker.stop_thread()

    app = FastAPI(
        title="KVKK-RAG Asistanı API",
        description="6698 Sayılı KVKK Hukuki Uyum ve Akıllı Retrieval API — "
                    "JWT kimlik, rol tabanlı izin (modul.aksiyon) ve kapsam katmanı",
        version="1.0.0",
        lifespan=lifespan,
    )
    register_cors(app)
    register_exceptions(app)

    for C in (controllers if controllers is not None else CONTROLLERS):
        C().register(app)

    if graphql:
        from strawberry.fastapi import GraphQLRouter

        from . import graphql_schema

        app.include_router(
            GraphQLRouter(graphql_schema.schema, context_getter=graphql_schema.get_context),
            prefix="/graphql", dependencies=[Depends(authenticate)])

    # Arayuz kokten servis edilir; API rotalarindan SONRA baglanmali
    if static:
        if (WEB_DIST / "index.html").exists():
            app.mount("/", SpaStaticFiles(directory=str(WEB_DIST), html=True), name="web")
        elif (WEB_ROOT / "index.html").exists():
            app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="web")

    return app
