"""Rol: izin demeti + her (modul, aksiyon) icin kapsam tanimi."""
from __future__ import annotations

import sqlite3
from typing import Iterable

from .base import Model
from .permission import GUARD, Permission
from .permission_scope import PermissionScope

# Bu roller kapsam kontrolunu atlar; dogrudan `all` kapsamina ve tum izinlere sahiptir.
BYPASS_ROLES: tuple[str, ...] = ("Superadmin", "Admin")


class Role(Model):
    table = "roles"
    fillable = ("name", "guard_name", "description")

    @classmethod
    def find_by_name(cls, conn: sqlite3.Connection, name: str, guard: str = GUARD) -> Role | None:
        return cls.query(conn).where("name", name).where("guard_name", guard).first()

    @classmethod
    def find_or_create(cls, conn: sqlite3.Connection, name: str,
                       description: str | None = None, guard: str = GUARD) -> Role:
        mevcut = cls.find_by_name(conn, name, guard)
        if mevcut:
            if description and mevcut.description != description:
                mevcut.update(conn, description=description)
            return mevcut
        return cls.create(conn, name=name, guard_name=guard, description=description)

    def is_bypass(self) -> bool:
        return self.name in BYPASS_ROLES

    # ---- izinler (Spatie HasPermissions) ----
    def permissions(self, conn: sqlite3.Connection) -> list[Permission]:
        return [Permission(dict(r)) for r in conn.execute(
            "SELECT p.* FROM permissions p JOIN role_has_permissions rp ON rp.permission_id = p.id "
            "WHERE rp.role_id = ? ORDER BY p.module, p.action", (self.id,))]

    def permission_names(self, conn: sqlite3.Connection) -> list[str]:
        return [p.name for p in self.permissions(conn)]

    def has_permission_to(self, conn: sqlite3.Connection, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM role_has_permissions rp JOIN permissions p ON p.id = rp.permission_id "
            "WHERE rp.role_id = ? AND p.name = ?", (self.id, name)).fetchone() is not None

    def give_permission_to(self, conn: sqlite3.Connection, *names: str) -> Role:
        for ad in names:
            p = Permission.find_or_create(conn, ad)
            conn.execute("INSERT OR IGNORE INTO role_has_permissions (permission_id, role_id) VALUES (?, ?)",
                         (p.id, self.id))
        conn.commit()
        self._permissions_changed(conn)
        return self

    def revoke_permission_to(self, conn: sqlite3.Connection, *names: str) -> Role:
        for ad in names:
            p = Permission.find_by_name(conn, ad)
            if p:
                conn.execute("DELETE FROM role_has_permissions WHERE permission_id = ? AND role_id = ?",
                             (p.id, self.id))
        conn.commit()
        self._permissions_changed(conn)
        return self

    def sync_permissions(self, conn: sqlite3.Connection, names: Iterable[str]) -> Role:
        conn.execute("DELETE FROM role_has_permissions WHERE role_id = ?", (self.id,))
        conn.commit()
        return self.give_permission_to(conn, *names)

    def _permissions_changed(self, conn: sqlite3.Connection) -> None:
        # Pivot tablo model olayi uretmez; Spatie'nin forgetCachedPermissions() karsiligi.
        from ..Services.permission_cache import flush_cache
        flush_cache()

    # ---- kapsamlar ----
    def scopes(self, conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
        return PermissionScope.matrix(conn, self.id)

    def set_scope(self, conn: sqlite3.Connection, module: str, action: str, scope: str) -> PermissionScope:
        return PermissionScope.set(conn, self.id, module, action, scope)

    def scope_for(self, conn: sqlite3.Connection, module: str, action: str) -> str:
        return PermissionScope.resolve(conn, [self.id], module, action)

    # ---- kullanicilar ----
    def user_ids(self, conn: sqlite3.Connection) -> list[int]:
        return [r[0] for r in conn.execute(
            "SELECT model_id FROM model_has_roles WHERE role_id = ? AND model_type = 'User'", (self.id,))]
