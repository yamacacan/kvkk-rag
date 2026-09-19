"""Izin katalogu: `modul.aksiyon`. Kapsamli moduller (SCOPED_MODULES) icin rol
basina kapsam da tanimlanir; digerlerinde yalnizca izin yeterlidir."""
from __future__ import annotations

import sqlite3

from ...app.Models.permission import Permission
from ...app.Models.permission_scope import SCOPED_MODULES  # noqa: F401 - role_seeder buradan alir

PERMISSIONS: dict[str, str] = {
    # envanter
    "inventory.view":    "Envanter satırlarını görüntüleme",
    "inventory.create":  "Envantere satır ekleme",
    "inventory.update":  "Envanter satırı düzenleme",
    "inventory.delete":  "Envanter satırı silme",
    "inventory.history": "Satır değişiklik geçmişini görme",
    "inventory.export":  "Envanteri Excel olarak dışa aktarma",
    "inventory.search":  "Envanterde anlamsal arama",
    "inventory.suggest": "Yapay zeka ile alan önerisi alma",
    "inventory.assign":  "Satıra sorumlu / denetçi atama",
    "inventory.reindex": "Envanter vektör indeksini yeniden kurma",
    # bulgular
    "findings.view":     "Uyum bulguları panosunu görme",
    # belgeler
    "documents.view":     "Belge şablonlarını ve önizlemeyi görme",
    "documents.generate": "Uyum belgesi üretme (docx/zip)",
    # acik riza kayitlari
    "consents.view":   "Açık rıza kayıtlarını görüntüleme",
    "consents.create": "Açık rıza kaydı oluşturma",
    "consents.update": "Açık rıza kaydı düzenleme (geri çekme dahil)",
    "consents.delete": "Açık rıza kaydı silme",
    # kurum profili
    "profile.view":   "Kurum profilini görme",
    "profile.update": "Kurum profilini güncelleme",
    # asistan / graf / taksonomi
    "chat.use":      "Mevzuat asistanını kullanma",
    "graph.view":    "Bilgi grafiği sorguları",
    "taxonomy.view": "Taksonomi listelerini görme",
    # yonetim
    "users.view":   "Kullanıcıları listeleme",
    "users.create": "Kullanıcı oluşturma",
    "users.update": "Kullanıcı düzenleme (rol/departman dahil)",
    "users.delete": "Kullanıcı silme",
    "roles.view":   "Rolleri ve izin kataloğunu görme",
    "roles.create": "Rol oluşturma",
    "roles.update": "Rol izin/kapsam düzenleme",
    "roles.delete": "Rol silme",
    "departments.view":   "Departmanları listeleme",
    "departments.create": "Departman oluşturma",
    "departments.update": "Departman düzenleme",
    "departments.delete": "Departman silme",
    "audit.view": "Denetim günlüğünü (audit trail) görme",
}


class PermissionSeeder:
    @staticmethod
    def run(conn: sqlite3.Connection) -> int:
        for ad, aciklama in PERMISSIONS.items():
            Permission.find_or_create(conn, ad, aciklama)
        return len(PERMISSIONS)
