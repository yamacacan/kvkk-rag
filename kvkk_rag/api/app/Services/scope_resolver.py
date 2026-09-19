"""(kullanici, modul, aksiyon) -> kapsam cozumleyici.

Sira:
 1. Superadmin / Admin  -> kapsam kontrolu atlanir, dogrudan `all`
 2. Rolsuz kullanici    -> `none`
 3. Onbellek            -> scope_v{v}_{roleIds}__{module}__{action}
 4. permission_scopes   -> rollerin tanimladigi kapsamlardan en yuksek oncelikli
    (cakisma cozumu: all > department > assigned > own > none); tanim yoksa `none`."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Iterable

from ..Models import permission_scope as ps
from ..Models.permission_scope import PermissionScope
from . import permission_cache

if TYPE_CHECKING:
    from ..Models.user import User


class ScopeResolver:
    def __init__(self, cache: permission_cache.PermissionCache | None = None) -> None:
        self.cache = cache or permission_cache.cache

    def resolve(self, conn: sqlite3.Connection, user: "User", module: str, action: str) -> str:
        if user.is_super(conn):
            return ps.ALL
        role_ids = user.role_ids(conn)
        if not role_ids:
            return ps.NONE
        anahtar = self.cache.scope_key(role_ids, module, action)
        return self.cache.remember(
            anahtar, lambda: self.resolve_for_roles(conn, role_ids, module, action))

    def resolve_for_roles(self, conn: sqlite3.Connection, role_ids: Iterable[int],
                          module: str, action: str) -> str:
        return PermissionScope.resolve(conn, role_ids, module, action)

    def permissions_for_roles(self, conn: sqlite3.Connection, role_ids: Iterable[int]) -> list[str]:
        # Spatie rol->izin haritasini da ayni surumlu onbellekte tutar
        role_ids = sorted(set(role_ids))
        if not role_ids:
            return []
        anahtar = self.cache.permissions_key(role_ids)

        def yukle() -> list[str]:
            yer = ", ".join("?" * len(role_ids))
            return sorted({r[0] for r in conn.execute(
                f"SELECT p.name FROM permissions p JOIN role_has_permissions rp ON rp.permission_id = p.id "
                f"WHERE rp.role_id IN ({yer})", role_ids)})

        return list(self.cache.remember(anahtar, yukle))

    def matrix(self, conn: sqlite3.Connection, user: "User") -> dict[str, dict[str, str]]:
        # Kapsamli modullerde sahip olunan her izin icin cozumlenmis kapsam:
        # {modul: {aksiyon: kapsam}}. Kapsamsiz moduller (chat, graph...) listelenmez.
        out: dict[str, dict[str, str]] = {}
        if user.is_super(conn):
            for r in conn.execute("SELECT module, action FROM permissions ORDER BY module, action"):
                if ps.is_scoped(r[0]):
                    out.setdefault(r[0], {})[r[1]] = ps.ALL
            return out
        for izin in sorted(user.permissions(conn)):
            if "." not in izin:
                continue
            module, action = izin.split(".", 1)
            if ps.is_scoped(module):
                out.setdefault(module, {})[action] = self.resolve(conn, user, module, action)
        return out
