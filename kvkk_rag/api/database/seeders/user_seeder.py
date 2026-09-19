"""Ilk yonetici. Hic kullanici yoksa KVKK_ADMIN_EMAIL / KVKK_ADMIN_PASSWORD ile
olusturulur; sifre verilmemisse rastgele uretilip loga yazilir (bir kez)."""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
from typing import Any

from ...app.Models.user import User

logger = logging.getLogger("kvkk_rag.api.seed")


class UserSeeder:
    @staticmethod
    def run(conn: sqlite3.Connection) -> dict[str, Any] | None:
        if User.query(conn).exists():
            return None
        email = os.getenv("KVKK_ADMIN_EMAIL", "admin@kvkk.local").strip().lower()
        sifre = os.getenv("KVKK_ADMIN_PASSWORD", "").strip()
        uretildi = False
        if not sifre:
            sifre, uretildi = secrets.token_urlsafe(12), True
        admin = User.register(conn, "Sistem Yöneticisi", email, sifre)
        admin.assign_role(conn, "Superadmin")
        if uretildi:
            logger.warning("İlk yönetici oluşturuldu: %s / şifre: %s  (KVKK_ADMIN_PASSWORD ile sabitleyin)",
                           email, sifre)
        else:
            logger.info("İlk yönetici oluşturuldu: %s", email)
        return {"id": admin.id, "email": email, "generated_password": sifre if uretildi else None}
