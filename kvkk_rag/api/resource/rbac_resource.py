from __future__ import annotations

from typing import Any

from .base import Resource


class UserResource(Resource):
    # context: conn (rol/izin/kapsam okumak icin), detailed (izin + kapsam matrisi)
    def to_array(self) -> dict[str, Any]:
        u, conn = self.item, self.context.get("conn")
        d = {"id": u.id, "name": u.name, "email": u.email,
             "is_active": bool(u.get("is_active", 1)),
             "department_id": u.get("department_id"),
             "last_login_at": u.get("last_login_at"),
             "created_at": u.get("created_at")}
        if conn is not None:
            d["roles"] = u.role_names(conn)
            d["departments"] = u.department_names(conn)
            d["department_ids"] = u.department_ids(conn)
            if self.context.get("detailed"):
                d["is_super"] = u.is_super(conn)
                d["permissions"] = sorted(u.permissions(conn)) if not u.is_super(conn) else ["*"]
                d["scopes"] = u.scope_matrix(conn)
        return d


class RoleResource(Resource):
    def to_array(self) -> dict[str, Any]:
        r, conn = self.item, self.context.get("conn")
        d = {"id": r.id, "name": r.name, "description": r.get("description"),
             "bypass": r.is_bypass()}
        if conn is not None:
            d["permissions"] = r.permission_names(conn)
            d["scopes"] = r.scopes(conn)
            d["user_count"] = len(r.user_ids(conn))
        return d


class DepartmentResource(Resource):
    def to_array(self) -> dict[str, Any]:
        d, conn = self.item, self.context.get("conn")
        out = {"id": d.id, "name": d.name, "description": d.get("description")}
        if conn is not None:
            ids = d.user_ids(conn)
            out["user_count"] = len(ids)
            out["envanter_sayisi"] = d.envanter_sayisi(conn)
            if self.context.get("detailed"):
                from ..app.Models.user import User
                out["users"] = [{"id": u.id, "name": u.name, "email": u.email, "roles": u.role_names(conn)}
                                for u in User.query(conn).where_in("id", ids).order_by("name").get()]
        return out
