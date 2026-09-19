"""Model gozlemcileri (Laravel Observer). Rol izinleri veya kapsamlar degisince
versiyonlu onbellek sifirlanir; kayit AppServiceProvider::boot karsiligi olan
app.boot() icinde yapilir."""
from __future__ import annotations

from ..Models.permission import Permission
from ..Models.permission_scope import PermissionScope
from ..Models.role import Role
from .permission_scope_observer import PermissionScopeObserver
from .role_observer import PermissionObserver, RoleObserver


def register() -> None:
    PermissionScope.observe(PermissionScopeObserver())
    Role.observe(RoleObserver())
    Permission.observe(PermissionObserver())
