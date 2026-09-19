"""Kapsam katmaninin bir modelden bekledigi arabirim (Laravel'deki trait karsiligi).

Sorgu seviyesi (ScopeFilter.apply) ve kayit seviyesi (User.has_scoped_permission)
dogrulama ayni sozlesmeyi kullanir:
  - scope_own / scope_assigned / scope_for_department : QueryBuilder'a SQL kosulu ekler
  - owned_by / assigned_to / in_departments           : tekil kayit icin bool
Model bu sinifi karistirir (mixin) ve sutun adlarini kendine gore tanimlar."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Iterable

from . import permission_scope as ps

if TYPE_CHECKING:
    from .base import QueryBuilder
    from .user import User


class Scopable:
    module: str = ""                 # kapsam tablosundaki modul adi
    owner_column: str = "created_by"  # own kapsami

    # ---- sorgu seviyesi ----
    @classmethod
    def scope_own(cls, query: "QueryBuilder", user: "User") -> "QueryBuilder":
        return query.where(f"{cls.table}.{cls.owner_column}", user.id)  # type: ignore[attr-defined]

    @classmethod
    def scope_assigned(cls, query: "QueryBuilder", user: "User") -> "QueryBuilder":
        raise NotImplementedError(f"{cls.__name__} icin assigned kapsami tanimli degil")

    @classmethod
    def scope_for_department(cls, query: "QueryBuilder",
                             department_ids: Iterable[int]) -> "QueryBuilder":
        raise NotImplementedError(f"{cls.__name__} icin department kapsami tanimli degil")

    # ---- kayit seviyesi ----
    def owned_by(self, user: "User") -> bool:
        return self.get(self.owner_column) == user.id  # type: ignore[attr-defined]

    def assigned_to(self, conn: sqlite3.Connection, user: "User") -> bool:
        raise NotImplementedError

    def in_departments(self, conn: sqlite3.Connection, department_ids: Iterable[int]) -> bool:
        raise NotImplementedError

    def matches_scope(self, conn: sqlite3.Connection, scope: str, user: "User") -> bool:
        if scope == ps.ALL:
            return True
        if scope == ps.NONE:
            return False
        if scope == ps.OWN:
            return self.owned_by(user)
        if scope == ps.ASSIGNED:
            return self.assigned_to(conn, user)
        if scope == ps.DEPARTMENT:
            return self.in_departments(conn, user.department_ids(conn))
        return False
