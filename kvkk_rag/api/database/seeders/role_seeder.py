"""Varsayilan roller: izin listesi + kapsamli moduller icin kapsam.

Superadmin / Admin  : kapsam kontrolunu atlar (tum izinler, `all`)
KVKK Sorumlusu      : tum operasyonel izinler, kapsam all (yonetim izinleri haric)
Denetçi             : kendisine atanan satirlar (assigned)
Birim Sorumlusu     : kendi departmani (department), tam CRUD
Veri Giriş          : yalnizca kendi olusturdugu satirlar (own)
İzleyici            : salt okunur, kapsam all

Varsayilan calisma (sync=False) yalnizca eksik rolleri olusturur; API ile
duzenlenmis mevcut roller korunur. sync=True (db:seed --sync) izin ve
kapsamlari bu tanima esitler."""
from __future__ import annotations

import sqlite3

from ...app.Models import permission_scope as ps
from ...app.Models.role import BYPASS_ROLES, Role
from .permission_seeder import PERMISSIONS, SCOPED_MODULES

OPERASYONEL = [p for p in PERMISSIONS
               if not p.startswith(("users.", "roles.", "departments."))]

ROLES: dict[str, dict] = {
    "Superadmin": {"description": "Sistem sahibi; kapsam kontrolünü atlar", "permissions": [], "scope": None},
    "Admin":      {"description": "Yönetici; kapsam kontrolünü atlar", "permissions": [], "scope": None},
    "KVKK Sorumlusu": {
        "description": "Veri sorumlusu irtibat kişisi; tüm envanter ve belgeler",
        "permissions": OPERASYONEL + ["users.view", "roles.view", "departments.view", "audit.view"],
        "scope": ps.ALL,
    },
    "Denetçi": {
        "description": "Kendisine atanan satırları denetler",
        "permissions": ["inventory.view", "inventory.update", "inventory.history", "inventory.export",
                        "inventory.search", "findings.view", "documents.view", "documents.generate",
                        "consents.view", "profile.view", "chat.use", "graph.view", "taxonomy.view"],
        "scope": ps.ASSIGNED,
    },
    "Birim Sorumlusu": {
        "description": "Kendi departmanının envanterini yönetir",
        "permissions": ["inventory.view", "inventory.create", "inventory.update", "inventory.delete",
                        "inventory.history", "inventory.export", "inventory.search", "inventory.suggest",
                        "inventory.assign", "findings.view", "documents.view", "documents.generate",
                        "consents.view", "consents.create", "consents.update", "consents.delete",
                        "profile.view", "chat.use", "graph.view", "taxonomy.view", "departments.view"],
        "scope": ps.DEPARTMENT,
    },
    "Veri Giriş": {
        "description": "Yalnızca kendi eklediği satırlar",
        "permissions": ["inventory.view", "inventory.create", "inventory.update", "inventory.history",
                        "inventory.search", "inventory.suggest", "findings.view",
                        "consents.view", "consents.create", "consents.update",
                        "chat.use", "taxonomy.view"],
        "scope": ps.OWN,
    },
    "İzleyici": {
        "description": "Salt okunur; tüm envanter ve bulgular",
        "permissions": ["inventory.view", "inventory.search", "findings.view", "documents.view",
                        "consents.view", "profile.view", "chat.use", "graph.view", "taxonomy.view"],
        "scope": ps.ALL,
    },
}


class RoleSeeder:
    @staticmethod
    def run(conn: sqlite3.Connection, sync: bool = False) -> int:
        olusan = 0
        for ad, tanim in ROLES.items():
            mevcut = Role.find_by_name(conn, ad)
            if mevcut and not sync:
                continue
            rol = mevcut or Role.find_or_create(conn, ad, tanim["description"])
            olusan += 0 if mevcut else 1
            if ad in BYPASS_ROLES:
                continue  # Gate::before ile her seyi yapabilir; izin/kapsam satiri gerekmez
            rol.sync_permissions(conn, tanim["permissions"])
            conn.execute("DELETE FROM permission_scopes WHERE role_id = ?", (rol.id,))
            conn.commit()
            for izin in tanim["permissions"]:
                module, action = izin.split(".", 1)
                if module in SCOPED_MODULES:
                    rol.set_scope(conn, module, action, tanim["scope"])
        return olusan
