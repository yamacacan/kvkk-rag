from __future__ import annotations

import sqlite3

from ..Events import PermissionsChanged, dispatch
from ..Services.permission_cache import flush_cache


class RoleObserver:
    # Rol silinince pivotlar CASCADE ile gider; onbellekteki izin/kapsam haritasi bayatlar.
    def deleted(self, role, conn: sqlite3.Connection) -> None:
        dispatch(PermissionsChanged(reason=f"rol silindi: {role.name}", version=flush_cache()))

    def updated(self, role, conn: sqlite3.Connection) -> None:
        dispatch(PermissionsChanged(reason=f"rol guncellendi: {role.name}", version=flush_cache()))


class PermissionObserver:
    def deleted(self, permission, conn: sqlite3.Connection) -> None:
        dispatch(PermissionsChanged(reason=f"izin silindi: {permission.name}", version=flush_cache()))
