from __future__ import annotations

import sqlite3
from typing import Any

from .department_seeder import DepartmentSeeder
from .permission_seeder import PermissionSeeder
from .role_seeder import RoleSeeder
from .user_seeder import UserSeeder


class DatabaseSeeder:
    @staticmethod
    def run(conn: sqlite3.Connection, with_admin: bool = True, sync: bool = False) -> dict[str, Any]:
        # sync=True: mevcut rollerin izin/kapsamlarini varsayilana esitler
        out: dict[str, Any] = {}
        out["permissions"] = PermissionSeeder.run(conn)
        out["roles"] = RoleSeeder.run(conn, sync=sync)
        out["departments"] = DepartmentSeeder.run(conn)
        if with_admin:
            out["admin"] = UserSeeder.run(conn)
        return out
