"""RBAC yonetimi: kullanicilar, roller (izin + kapsam matrisi), departmanlar, izin
katalogu. Superadmin/Admin disindaki roller bu uclara ancak users.* / roles.* /
departments.* izinleriyle ulasir."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import Depends, HTTPException, Request

from ....database.connection import get_db
from ....resource import DepartmentResource, RoleResource, UserResource
from ...Models import permission_scope as ps
from ...Models.audit_log import AuditLog
from ...Models.department import Department
from ...Models.permission import Permission
from ...Models.role import BYPASS_ROLES, Role
from ...Models.user import User
from ...Services.permission_cache import cache, flush_cache
from ..Middleware.authenticate import authenticate
from ..Request.rbac import (DepartmentRequest, RoleCloneRequest, RoleStoreRequest, RoleUpdateRequest,
                            ScopeSyncRequest, UserStoreRequest, UserUpdateRequest)
from .base import Controller, route


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    return ileri.split(",")[0].strip() if ileri else (request.client.host if request.client else None)


def _departmanlari_dogrula(conn: sqlite3.Connection, ids: list[int] | None, tekil: int | None) -> None:
    for d in [*(ids or []), *([tekil] if tekil else [])]:
        if Department.find(conn, d) is None:
            raise HTTPException(422, f"Departman bulunamadı: {d}")


def _izinleri_dogrula(conn: sqlite3.Connection, izinler: list[str]) -> None:
    # Katalogda olmayan izin (yazim hatasi) sessizce olusmasin
    bilinmeyen = [ad for ad in izinler if Permission.find_by_name(conn, ad) is None]
    if bilinmeyen:
        raise HTTPException(422, f"Bilinmeyen izin: {', '.join(bilinmeyen)}")


def _rolleri_dogrula(conn: sqlite3.Connection, roller: list[str], user: User) -> None:
    for ad in roller:
        if Role.find_by_name(conn, ad) is None:
            raise HTTPException(422, f"Rol bulunamadı: {ad}")
        # Superadmin/Admin rolunu yalnizca bu rollerden biri verebilir (yetki yukseltme onlemi)
        if ad in BYPASS_ROLES and not user.is_super(conn):
            raise HTTPException(403, f"'{ad}' rolünü yalnızca yönetici atayabilir.")


class UserController(Controller):
    prefix = "/api/users"
    tags = ["rbac"]
    middleware = (authenticate,)

    @route("GET", "", permission="users.view")
    def index(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"kullanicilar": UserResource.collection(User.all(conn), conn=conn)}

    @route("POST", "", permission="users.create")
    def store(self, req: UserStoreRequest, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if User.find_by_email(conn, req.email):
            raise HTTPException(422, "Bu e-posta zaten kayıtlı.")
        _rolleri_dogrula(conn, req.roles, user)
        _departmanlari_dogrula(conn, req.departments, req.department_id)
        yeni = User.register(conn, req.name, req.email, req.password,
                             department_id=req.department_id, is_active=req.is_active)
        yeni.assign_role(conn, *req.roles)
        yeni.sync_departments(conn, req.departments)
        AuditLog.record(conn, "users.create", actor=user, target=yeni,
                        after={"email": yeni.email, "roles": req.roles, "departments": req.departments}, ip=_ip(request))
        return {"user": UserResource.make(yeni, conn=conn, detailed=True)}

    @route("GET", "/{user_id}", permission="users.view")
    def show(self, user_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        hedef = self.find_or_fail(User.find(conn, user_id), "Kullanıcı bulunamadı")
        return {"user": UserResource.make(hedef, conn=conn, detailed=True)}

    @route("PATCH", "/{user_id}", permission="users.update")
    def update(self, user_id: int, req: UserUpdateRequest, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        hedef = self.find_or_fail(User.find(conn, user_id), "Kullanıcı bulunamadı")
        if hedef.is_super(conn) and not user.is_super(conn):
            raise HTTPException(403, "Yönetici hesaplarını yalnızca yöneticiler düzenleyebilir.")
        once = {"name": hedef.name, "email": hedef.email, "is_active": hedef.active,
                "roles": hedef.role_names(conn), "departments": hedef.department_ids(conn)}
        degisiklik: dict[str, Any] = {}
        if req.name is not None:
            degisiklik["name"] = req.name.strip()
        if req.email is not None:
            mevcut = User.find_by_email(conn, req.email)
            if mevcut and mevcut.id != hedef.id:
                raise HTTPException(422, "Bu e-posta zaten kayıtlı.")
            degisiklik["email"] = req.email.strip().lower()
        if req.is_active is not None:
            if hedef.id == user.id and not req.is_active:
                raise HTTPException(422, "Kendi hesabınızı pasife alamazsınız.")
            degisiklik["is_active"] = 1 if req.is_active else 0
        if req.department_id is not None:
            _departmanlari_dogrula(conn, None, req.department_id)
            degisiklik["department_id"] = req.department_id
        if degisiklik:
            hedef.update(conn, **degisiklik)
        if req.password:
            hedef.set_password(conn, req.password)
        if req.roles is not None:
            _rolleri_dogrula(conn, req.roles, user)
            hedef.sync_roles(conn, req.roles)
        if req.departments is not None:
            _departmanlari_dogrula(conn, req.departments, None)
            hedef.sync_departments(conn, req.departments)
        hedef.forget_cached()
        sonra = {"name": hedef.name, "email": hedef.email, "is_active": hedef.active,
                 "roles": hedef.role_names(conn), "departments": hedef.department_ids(conn),
                 "password": "değişti" if req.password else None}
        AuditLog.record(conn, "users.update", actor=user, target=hedef, before=once, after=sonra, ip=_ip(request))
        return {"user": UserResource.make(hedef, conn=conn, detailed=True)}

    @route("DELETE", "/{user_id}", permission="users.delete")
    def destroy(self, user_id: int, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        hedef = self.find_or_fail(User.find(conn, user_id), "Kullanıcı bulunamadı")
        if hedef.id == user.id:
            raise HTTPException(422, "Kendi hesabınızı silemezsiniz.")
        if hedef.is_super(conn) and not user.is_super(conn):
            raise HTTPException(403, "Yönetici hesaplarını yalnızca yöneticiler silebilir.")
        AuditLog.record(conn, "users.delete", actor=user, target=hedef,
                        before={"email": hedef.email, "roles": hedef.role_names(conn)}, ip=_ip(request))
        hedef.delete(conn)
        return {"silindi": user_id}


class RoleController(Controller):
    prefix = "/api/roles"
    tags = ["rbac"]
    middleware = (authenticate,)

    @route("GET", "", permission="roles.view")
    def index(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"roller": RoleResource.collection(Role.all(conn), conn=conn),
                "kapsamlar": [{"ad": s, "oncelik": ps.priority(s), "aciklama": ps.SCOPE_ACIKLAMA[s]}
                              for s in ps.SCOPES],
                "atlayan_roller": list(BYPASS_ROLES),
                "kapsamli_moduller": list(ps.SCOPED_MODULES)}

    @route("POST", "", permission="roles.create")
    def store(self, req: RoleStoreRequest, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if Role.find_by_name(conn, req.name):
            raise HTTPException(422, "Bu rol adı zaten var.")
        _izinleri_dogrula(conn, req.permissions)
        rol = Role.create(conn, name=req.name.strip(), guard_name="api", description=req.description)
        rol.give_permission_to(conn, *req.permissions)
        for s in req.scopes:
            rol.set_scope(conn, s.module, s.action, s.scope)
        AuditLog.record(conn, "roles.create", actor=user, target=rol,
                        after={"permissions": req.permissions, "scopes": rol.scopes(conn)}, ip=_ip(request))
        return {"rol": RoleResource.make(rol, conn=conn)}

    @route("POST", "/{role_id}/clone", permission="roles.create")
    def clone(self, role_id: int, req: RoleCloneRequest, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Izinleri ve kapsamlari kopyalar; bypass rolleri klonlanmaz (kapsam tanimlari yoktur)
        kaynak = self.find_or_fail(Role.find(conn, role_id), "Rol bulunamadı")
        if kaynak.is_bypass():
            raise HTTPException(422, "Superadmin/Admin rolleri klonlanamaz.")
        if Role.find_by_name(conn, req.name.strip()):
            raise HTTPException(422, "Bu rol adı zaten var.")
        rol = Role.create(conn, name=req.name.strip(), guard_name="api",
                          description=kaynak.get("description"))
        rol.give_permission_to(conn, *kaynak.permission_names(conn))
        for module, aksiyonlar in kaynak.scopes(conn).items():
            for action, scope in aksiyonlar.items():
                rol.set_scope(conn, module, action, scope)
        AuditLog.record(conn, "roles.clone", actor=user, target=rol, before={"kaynak": kaynak.name}, ip=_ip(request))
        return {"rol": RoleResource.make(rol, conn=conn)}

    @route("GET", "/{role_id}", permission="roles.view")
    def show(self, role_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        rol = self.find_or_fail(Role.find(conn, role_id), "Rol bulunamadı")
        return {"rol": RoleResource.make(rol, conn=conn)}

    @route("PATCH", "/{role_id}", permission="roles.update")
    def update(self, role_id: int, req: RoleUpdateRequest, request: Request, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        rol = self.find_or_fail(Role.find(conn, role_id), "Rol bulunamadı")
        if rol.is_bypass() and not user.is_super(conn):
            raise HTTPException(403, "Yönetici rollerini yalnızca yöneticiler düzenleyebilir.")
        once = {"name": rol.name, "permissions": rol.permission_names(conn), "scopes": rol.scopes(conn)}
        degisiklik: dict[str, Any] = {}
        if req.name is not None and req.name.strip() != rol.name:
            if Role.find_by_name(conn, req.name.strip()):
                raise HTTPException(422, "Bu rol adı zaten var.")
            degisiklik["name"] = req.name.strip()
        if req.description is not None:
            degisiklik["description"] = req.description
        if degisiklik:
            rol.update(conn, **degisiklik)
        if req.permissions is not None:
            _izinleri_dogrula(conn, req.permissions)
            rol.sync_permissions(conn, req.permissions)
        if req.scopes is not None:
            conn.execute("DELETE FROM permission_scopes WHERE role_id = ?", (rol.id,))
            conn.commit()
            for s in req.scopes:
                rol.set_scope(conn, s.module, s.action, s.scope)
            flush_cache()  # silme model olayi uretmedi; surumu yine de artir
        AuditLog.record(conn, "roles.update", actor=user, target=rol, before=once,
                        after={"name": rol.name, "permissions": rol.permission_names(conn), "scopes": rol.scopes(conn)},
                        ip=_ip(request))
        return {"rol": RoleResource.make(rol, conn=conn)}

    @route("PUT", "/{role_id}/scopes", permission="roles.update")
    def scopes(self, role_id: int, req: ScopeSyncRequest, user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Yalnizca verilen (modul, aksiyon) ciftleri guncellenir; digerleri korunur
        rol = self.find_or_fail(Role.find(conn, role_id), "Rol bulunamadı")
        if rol.is_bypass():
            raise HTTPException(422, "Superadmin/Admin kapsam kontrolünü atlar; kapsam tanımlanmaz.")
        for s in req.scopes:
            rol.set_scope(conn, s.module, s.action, s.scope)
        return {"rol": RoleResource.make(rol, conn=conn)}

    @route("DELETE", "/{role_id}", permission="roles.delete")
    def destroy(self, role_id: int, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        rol = self.find_or_fail(Role.find(conn, role_id), "Rol bulunamadı")
        if rol.is_bypass():
            raise HTTPException(422, "Superadmin ve Admin rolleri silinemez.")
        if rol.user_ids(conn):
            raise HTTPException(422, "Bu role atanmış kullanıcılar var; önce rolü kullanıcılardan kaldırın.")
        AuditLog.record(conn, "roles.delete", actor=user, target=rol,
                        before={"permissions": rol.permission_names(conn)}, ip=_ip(request))
        rol.delete(conn)
        return {"silindi": role_id}


class PermissionController(Controller):
    prefix = "/api/permissions"
    tags = ["rbac"]
    middleware = (authenticate,)

    @route("GET", "", permission="roles.view")
    def index(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"izinler": Permission.by_module(conn), "bicim": "modul.aksiyon",
                "kapsamlar": ps.SCOPE_ACIKLAMA}

    @route("POST", "/cache-reset", permission="roles.update")
    def cache_reset(self) -> dict[str, Any]:
        # Spatie `permission:cache-reset` karsiligi: O(1) surum artirimi
        return {"surum": flush_cache(), "isabet": cache.hits, "kacirma": cache.misses}


class DepartmentController(Controller):
    prefix = "/api/departments"
    tags = ["rbac"]
    middleware = (authenticate,)

    @staticmethod
    def _uyeleri_esle(conn: sqlite3.Connection, d: Department, user_ids: list[int]) -> None:
        # Uye kumesi: coklu iliski (user_departments) uzerinden; tekil department_id korunur
        for uid in user_ids:
            if User.find(conn, uid) is None:
                raise HTTPException(422, f"Kullanıcı bulunamadı: {uid}")
        mevcut = set(d.user_ids(conn))
        istenen = set(user_ids)
        for uid in istenen - mevcut:
            conn.execute("INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)", (uid, d.id))
        for uid in mevcut - istenen:
            conn.execute("DELETE FROM user_departments WHERE user_id = ? AND department_id = ?", (uid, d.id))
            conn.execute("UPDATE users SET department_id = NULL WHERE id = ? AND department_id = ?", (uid, d.id))
        conn.commit()

    @route("GET", "", permission="departments.view")
    def index(self, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"departmanlar": DepartmentResource.collection(Department.all(conn), conn=conn)}

    @route("POST", "", permission="departments.create")
    def store(self, req: DepartmentRequest, request: Request, user: User = Depends(authenticate),
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if Department.find_by_name(conn, req.name.strip()):
            raise HTTPException(422, "Bu departman zaten var.")
        d = Department.create(conn, name=req.name.strip(), description=req.description)
        if req.users is not None:
            self._uyeleri_esle(conn, d, req.users)
        AuditLog.record(conn, "departments.create", actor=user, target=d, after={"users": req.users}, ip=_ip(request))
        return {"departman": DepartmentResource.make(d, conn=conn, detailed=True)}

    @route("GET", "/{department_id}", permission="departments.view")
    def show(self, department_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        d = self.find_or_fail(Department.find(conn, department_id), "Departman bulunamadı")
        return {"departman": DepartmentResource.make(d, conn=conn, detailed=True)}

    @route("PATCH", "/{department_id}", permission="departments.update")
    def update(self, department_id: int, req: DepartmentRequest, request: Request,
               user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        d = self.find_or_fail(Department.find(conn, department_id), "Departman bulunamadı")
        mevcut = Department.find_by_name(conn, req.name.strip())
        if mevcut and mevcut.id != d.id:
            raise HTTPException(422, "Bu departman zaten var.")
        once = {"name": d.name, "description": d.get("description"), "users": d.user_ids(conn)}
        eski_ad = d.name
        d.update(conn, name=req.name.strip(), description=req.description)
        if eski_ad != d.name:
            # envanterdeki birim metni departman adiyla eslesir; kapsam kopmasin
            conn.execute("UPDATE envanter SET birim = ? WHERE birim = ?", (d.name, eski_ad))
            conn.commit()
        if req.users is not None:
            self._uyeleri_esle(conn, d, req.users)
        AuditLog.record(conn, "departments.update", actor=user, target=d, before=once,
                        after={"name": d.name, "description": d.get("description"), "users": d.user_ids(conn)},
                        ip=_ip(request))
        return {"departman": DepartmentResource.make(d, conn=conn, detailed=True)}

    @route("DELETE", "/{department_id}", permission="departments.delete")
    def destroy(self, department_id: int, request: Request, user: User = Depends(authenticate),
                conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        d = self.find_or_fail(Department.find(conn, department_id), "Departman bulunamadı")
        if d.user_ids(conn):
            raise HTTPException(422, "Bu birime bağlı kullanıcılar var; önce üyeleri çıkarın.")
        AuditLog.record(conn, "departments.delete", actor=user, target=d, ip=_ip(request))
        d.delete(conn)
        return {"silindi": department_id}
