"""2. kademe: veri izolasyon katmani. (role_id, module, action) => scope uclusu.

Kapsam oncelik sirasi: all (5) > department (4) > assigned (3) > own (2) > none (1).
Kullanici birden fazla role sahipse ilgili modul/aksiyon icin en yuksek puanli
kapsam secilir (bkz. Services/scope_resolver.py)."""
from __future__ import annotations

import sqlite3
from typing import Iterable

from .base import Model

ALL, DEPARTMENT, ASSIGNED, OWN, NONE = "all", "department", "assigned", "own", "none"

SCOPE_PRIORITY: dict[str, int] = {ALL: 5, DEPARTMENT: 4, ASSIGNED: 3, OWN: 2, NONE: 1}
SCOPES: tuple[str, ...] = tuple(SCOPE_PRIORITY)

SCOPE_ACIKLAMA: dict[str, str] = {
    ALL: "Moduldeki tum verilere erisim",
    DEPARTMENT: "Yalnizca kullanicinin bagli oldugu departman(lar)a ait veriler",
    ASSIGNED: "Kullanicinin sorumlu, lider denetci veya ekip uyesi oldugu kayitlar",
    OWN: "Kullanicinin bizzat olusturdugu kayitlar",
    NONE: "Modulde hicbir kayda erisemez",
}

# Kapsam tanimi olmayan (permission var, satir yok) durumda uygulanan varsayilan.
# Guvenli taraf: kayit gorunmez. Seeder her rol icin acikca tanimlar.
DEFAULT_SCOPE = NONE

# Kayit seviyesi kapsam uygulanan moduller (own/assigned/department anlamli).
# Digerlerinde (chat, graph, users...) yalnizca izin yeterlidir; kapsam sorulmaz.
SCOPED_MODULES: tuple[str, ...] = ("inventory", "findings", "documents", "consents")


def is_scoped(module: str) -> bool:
    return module in SCOPED_MODULES


def is_valid(scope: str) -> bool:
    return scope in SCOPE_PRIORITY


def priority(scope: str) -> int:
    return SCOPE_PRIORITY.get(scope, 0)


def highest(scopes: Iterable[str]) -> str:
    # Coklu rol cakisma cozumu: en genis kapsam (en yuksek oncelik puani) kazanir.
    en_iyi = DEFAULT_SCOPE
    for s in scopes:
        if priority(s) > priority(en_iyi):
            en_iyi = s
    return en_iyi


class PermissionScope(Model):
    table = "permission_scopes"
    fillable = ("role_id", "module", "action", "scope")

    @classmethod
    def for_roles(cls, conn: sqlite3.Connection, role_ids: Iterable[int],
                  module: str, action: str) -> list[str]:
        return (cls.query(conn)
                .where_in("role_id", role_ids)
                .where("module", module)
                .where("action", action)
                .pluck("scope"))

    @classmethod
    def resolve(cls, conn: sqlite3.Connection, role_ids: Iterable[int],
                module: str, action: str) -> str:
        return highest(cls.for_roles(conn, role_ids, module, action))

    @classmethod
    def set(cls, conn: sqlite3.Connection, role_id: int, module: str, action: str,
            scope: str) -> PermissionScope:
        if not is_valid(scope):
            raise ValueError(f"Geçersiz kapsam: {scope!r} (beklenen: {', '.join(SCOPES)})")
        return cls.update_or_create(
            conn, {"role_id": role_id, "module": module, "action": action}, scope=scope)

    @classmethod
    def matrix(cls, conn: sqlite3.Connection, role_id: int) -> dict[str, dict[str, str]]:
        # {modul: {aksiyon: kapsam}} - rol duzenleme ekrani icin
        out: dict[str, dict[str, str]] = {}
        for s in cls.query(conn).where("role_id", role_id).order_by("module").order_by("action").get():
            out.setdefault(s.module, {})[s.action] = s.scope
        return out
