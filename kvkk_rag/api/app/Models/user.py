"""Kullanici: Spatie HasRoles davranisi (roles, permissions, can) + kapsam
cozumleme (scope_for, has_scoped_permission).

Rol/izin/departman okumalari istek suresince ornek uzerinde ezberlenir; kullanici
nesnesi her istekte jetondan yeniden yuklendigi icin bayatlama sorunu olmaz."""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from ..Services import hashing
from .base import Model
from .permission import Permission
from .role import BYPASS_ROLES, Role


class User(Model):
    table = "users"
    fillable = ("name", "email", "password", "department_id", "is_active", "last_login_at")
    hidden = ("password",)

    def __init__(self, attributes: dict[str, Any] | None = None) -> None:
        super().__init__(attributes)
        self._cache: dict[str, Any] = {}

    def forget_cached(self) -> None:
        self._cache.clear()

    # ---- kimlik ----
    @classmethod
    def find_by_email(cls, conn: sqlite3.Connection, email: str) -> User | None:
        return cls.query(conn).where("email", email.strip().lower()).first()

    @classmethod
    def register(cls, conn: sqlite3.Connection, name: str, email: str, password: str,
                 department_id: int | None = None, is_active: bool = True) -> User:
        return cls.create(conn, name=name.strip(), email=email.strip().lower(),
                          password=hashing.make(password), department_id=department_id,
                          is_active=1 if is_active else 0)

    def set_password(self, conn: sqlite3.Connection, password: str) -> None:
        self.update(conn, password=hashing.make(password))

    def check_password(self, password: str) -> bool:
        return hashing.check(password, self.password)

    @property
    def active(self) -> bool:
        return bool(self.get("is_active", 1))

    # ---- roller (Spatie HasRoles) ----
    def roles(self, conn: sqlite3.Connection) -> list[Role]:
        if "roles" not in self._cache:
            self._cache["roles"] = [Role(dict(r)) for r in conn.execute(
                "SELECT r.* FROM roles r JOIN model_has_roles mr ON mr.role_id = r.id "
                "WHERE mr.model_type = 'User' AND mr.model_id = ? ORDER BY r.id", (self.id,))]
        return self._cache["roles"]

    def role_ids(self, conn: sqlite3.Connection) -> list[int]:
        return sorted(r.id for r in self.roles(conn))

    def role_names(self, conn: sqlite3.Connection) -> list[str]:
        return [r.name for r in self.roles(conn)]

    def has_role(self, conn: sqlite3.Connection, *names: str) -> bool:
        sahip = set(self.role_names(conn))
        return any(n in sahip for n in names)

    def has_any_role(self, conn: sqlite3.Connection, names: Iterable[str]) -> bool:
        return self.has_role(conn, *names)

    def is_super(self, conn: sqlite3.Connection) -> bool:
        # Superadmin ve Admin kapsam kontrolunu atlar
        return self.has_role(conn, *BYPASS_ROLES)

    def assign_role(self, conn: sqlite3.Connection, *roles: str | Role) -> User:
        for r in roles:
            rol = r if isinstance(r, Role) else Role.find_by_name(conn, r)
            if not rol:
                raise ValueError(f"Rol bulunamadı: {r}")
            conn.execute("INSERT OR IGNORE INTO model_has_roles (role_id, model_type, model_id) "
                         "VALUES (?, 'User', ?)", (rol.id, self.id))
        conn.commit()
        self.forget_cached()
        return self

    def remove_role(self, conn: sqlite3.Connection, *roles: str | Role) -> User:
        for r in roles:
            rol = r if isinstance(r, Role) else Role.find_by_name(conn, r)
            if rol:
                conn.execute("DELETE FROM model_has_roles WHERE role_id = ? AND model_type = 'User' "
                             "AND model_id = ?", (rol.id, self.id))
        conn.commit()
        self.forget_cached()
        return self

    def sync_roles(self, conn: sqlite3.Connection, roles: Iterable[str | Role]) -> User:
        conn.execute("DELETE FROM model_has_roles WHERE model_type = 'User' AND model_id = ?", (self.id,))
        conn.commit()
        self.forget_cached()
        return self.assign_role(conn, *roles)

    # ---- izinler ----
    def direct_permissions(self, conn: sqlite3.Connection) -> set[str]:
        return {r[0] for r in conn.execute(
            "SELECT p.name FROM permissions p JOIN model_has_permissions mp ON mp.permission_id = p.id "
            "WHERE mp.model_type = 'User' AND mp.model_id = ?", (self.id,))}

    def permissions(self, conn: sqlite3.Connection) -> set[str]:
        # roller uzerinden gelenler (versiyonlu onbellek) + dogrudan verilenler
        if "permissions" not in self._cache:
            from ..Services.scope_resolver import ScopeResolver
            rol_izinleri = ScopeResolver().permissions_for_roles(conn, self.role_ids(conn))
            self._cache["permissions"] = set(rol_izinleri) | self.direct_permissions(conn)
        return self._cache["permissions"]

    def can(self, conn: sqlite3.Connection, permission: str) -> bool:
        # Spatie `can`: Gate::before ile Superadmin/Admin her seyi yapabilir
        if not self.active:
            return False
        if self.is_super(conn):
            return True
        return permission in self.permissions(conn)

    def can_any(self, conn: sqlite3.Connection, permissions: Iterable[str]) -> bool:
        return any(self.can(conn, p) for p in permissions)

    def give_permission_to(self, conn: sqlite3.Connection, *names: str) -> User:
        for ad in names:
            p = Permission.find_or_create(conn, ad)
            conn.execute("INSERT OR IGNORE INTO model_has_permissions (permission_id, model_type, model_id) "
                         "VALUES (?, 'User', ?)", (p.id, self.id))
        conn.commit()
        self.forget_cached()
        return self

    def revoke_permission_to(self, conn: sqlite3.Connection, *names: str) -> User:
        for ad in names:
            p = Permission.find_by_name(conn, ad)
            if p:
                conn.execute("DELETE FROM model_has_permissions WHERE permission_id = ? "
                             "AND model_type = 'User' AND model_id = ?", (p.id, self.id))
        conn.commit()
        self.forget_cached()
        return self

    # ---- departmanlar ----
    def department_ids(self, conn: sqlite3.Connection) -> list[int]:
        # tekil (users.department_id) + coklu (user_departments) birlesimi
        if "department_ids" not in self._cache:
            ids = {r[0] for r in conn.execute(
                "SELECT department_id FROM user_departments WHERE user_id = ?", (self.id,))}
            if self.get("department_id"):
                ids.add(self.department_id)
            self._cache["department_ids"] = sorted(ids)
        return self._cache["department_ids"]

    def department_names(self, conn: sqlite3.Connection) -> list[str]:
        from .department import Department
        return Department.names_for(conn, self.department_ids(conn))

    def sync_departments(self, conn: sqlite3.Connection, ids: Iterable[int]) -> User:
        conn.execute("DELETE FROM user_departments WHERE user_id = ?", (self.id,))
        for d in set(ids):
            conn.execute("INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)",
                         (self.id, d))
        conn.commit()
        self.forget_cached()
        return self

    # ---- kapsam (2. kademe) ----
    def scope_for(self, conn: sqlite3.Connection, module: str, action: str) -> str:
        from ..Services.scope_resolver import ScopeResolver
        return ScopeResolver().resolve(conn, self, module, action)

    def has_scoped_permission(self, conn: sqlite3.Connection, module: str, action: str,
                              record: Any | None = None) -> bool:
        """Tekil kayit uzerinde islem: once Spatie izni (can), sonra kaydin sahibi /
        departmani / atamasi kullanicinin kapsamiyla uyusuyor mu? Kayit verilmezse
        (create gibi) kapsamin `none` olmamasi yeterlidir."""
        if not self.can(conn, f"{module}.{action}"):
            return False
        if self.is_super(conn):
            return True
        scope = self.scope_for(conn, module, action)
        if record is None:
            from .permission_scope import NONE
            return scope != NONE
        return record.matches_scope(conn, scope, self)

    def scope_matrix(self, conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
        # {modul: {aksiyon: kapsam}} - arayuzun neyi gostereceğini bilmesi icin
        from ..Services.scope_resolver import ScopeResolver
        return ScopeResolver().matrix(conn, self)

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["is_active"] = bool(d.get("is_active", 1))
        return d
