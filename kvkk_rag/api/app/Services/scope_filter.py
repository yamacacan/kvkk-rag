"""Sorgu seviyesi filtreleme. Listeleme yapilirken kullanicinin kapsamini
QueryBuilder'a otomatik SQL kosulu olarak ekler:

  own        -> WHERE created_by = user.id
  assigned   -> WHERE sorumlu_id = user.id OR EXISTS (denetciler ...)
  department -> modelin scope_for_department(department_ids) kosulu
  none       -> WHERE 0 = 1
  all        -> kosul yok

Model, Scopable arabirimini uygular; sutun adlarini kendisi bilir."""
from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from ..Models import permission_scope as ps
from ..Models.base import QueryBuilder
from .scope_resolver import ScopeResolver

if TYPE_CHECKING:
    from ..Models.user import User


class ScopeFilter:
    @staticmethod
    def apply(query: QueryBuilder, user: "User", module: str, action: str,
              conn: sqlite3.Connection | None = None, model: type | None = None) -> QueryBuilder:
        conn = conn or query.conn
        model = model or query.model
        if model is None:
            raise ValueError("ScopeFilter.apply icin model gerekli (Scopable)")
        scope = ScopeResolver().resolve(conn, user, module, action)
        query.scope_applied = scope
        if scope == ps.ALL:
            return query
        if scope == ps.NONE:
            return query.where_raw("0 = 1")
        if scope == ps.OWN:
            return model.scope_own(query, user)
        if scope == ps.ASSIGNED:
            return model.scope_assigned(query, user)
        if scope == ps.DEPARTMENT:
            return model.scope_for_department(query, user.department_ids(conn))
        return query.where_raw("0 = 1")  # bilinmeyen kapsam: guvenli taraf

    @staticmethod
    def resolve(conn: sqlite3.Connection, user: "User", module: str, action: str) -> str:
        return ScopeResolver().resolve(conn, user, module, action)
