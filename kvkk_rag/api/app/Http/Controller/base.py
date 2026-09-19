"""Sinif tabanli controller (Laravel Controller karsiligi) FastAPI uzerinde.

    class InventoryController(Controller):
        prefix = "/api/inventory"
        middleware = (authenticate,)                # tum rotalara

        @route("GET", "", permission="inventory.view")   # 1. kademe: Spatie izni
        def index(self, user: User = Depends(authenticate), conn = Depends(get_db)):
            q = ScopeFilter.apply(Envanter.query(conn), user, "inventory", "view")  # 2. kademe
            ...

Rotalar tanim sirasiyla kaydedilir (sabit yollar, {param} yollarindan once
yazilmali). `permission=` / `role=` Spatie middleware'lerinin karsiligidir; kayit
seviyesi kapsam dogrulamasi icin `self.authorize(...)` kullanilir."""
from __future__ import annotations

import itertools
import sqlite3
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException

from ...Models.user import User
from ..Middleware.authorize import permission as permission_dep
from ..Middleware.authorize import role as role_dep

_sira = itertools.count()


def route(method: str, path: str, *, permission: str | tuple[str, ...] | None = None,
          role: str | tuple[str, ...] | None = None, **kwargs: Any) -> Callable:
    def deco(fn: Callable) -> Callable:
        rotalar = getattr(fn, "_routes", None)
        if rotalar is None:
            rotalar = []
            fn._routes = rotalar  # type: ignore[attr-defined]
            fn._order = next(_sira)  # type: ignore[attr-defined]
        rotalar.append({"method": method.upper(), "path": path,
                        "permission": (permission,) if isinstance(permission, str) else permission,
                        "role": (role,) if isinstance(role, str) else role,
                        "kwargs": kwargs})
        return fn
    return deco


class Controller:
    prefix: str = ""
    tags: list[str] = []
    middleware: tuple[Callable, ...] = ()

    def router(self) -> APIRouter:
        router = APIRouter(prefix=self.prefix, tags=list(self.tags),
                           dependencies=[Depends(m) for m in self.middleware])
        metotlar = [getattr(self, ad) for ad in dir(type(self))
                    if not ad.startswith("_") and hasattr(getattr(type(self), ad), "_routes")]
        for m in sorted(metotlar, key=lambda f: f._order):
            for r in m._routes:
                deps = []
                if r["permission"]:
                    deps.append(Depends(permission_dep(*r["permission"])))
                if r["role"]:
                    deps.append(Depends(role_dep(*r["role"])))
                router.add_api_route(r["path"], m, methods=[r["method"]],
                                     dependencies=deps, **r["kwargs"])
        return router

    def register(self, app: FastAPI) -> None:
        app.include_router(self.router())

    # ---- yardimcilar ----
    @staticmethod
    def authorize(conn: sqlite3.Connection, user: User, module: str, action: str,
                  record: Any | None = None) -> None:
        # Kayit/model seviyesi dogrulama: Spatie izni + kapsam uyusmasi
        if not user.has_scoped_permission(conn, module, action, record):
            if record is None:
                raise HTTPException(403, f"'{module}.{action}' için yetkiniz yok.")
            raise HTTPException(403, "Bu kayıt yetki kapsamınızın dışında.")

    @staticmethod
    def abort(status: int, message: str) -> None:
        raise HTTPException(status, message)

    @staticmethod
    def find_or_fail(model: Any | None, message: str = "Kayıt bulunamadı") -> Any:
        if model is None:
            raise HTTPException(404, message)
        return model
