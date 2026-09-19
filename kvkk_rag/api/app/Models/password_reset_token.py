"""Sifre sifirlama jetonu (Laravel password_reset_tokens). E-posta basina tek
satir; duz jeton yalnizca baglantida yer alir, tabloda SHA-256 ozeti durur."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .base import Model, now

TTL_MINUTES = int(os.getenv("KVKK_PASSWORD_RESET_TTL_MINUTES", "60"))


def _hash(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class PasswordResetToken(Model):
    table = "password_reset_tokens"
    primary_key = "email"
    fillable = ("email", "token", "created_at")
    timestamps = False

    @classmethod
    def issue(cls, conn: sqlite3.Connection, email: str) -> str:
        email = email.strip().lower()
        plain = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM password_reset_tokens WHERE email = ?", (email,))
        conn.commit()
        cls.create(conn, email=email, token=_hash(plain), created_at=now())
        return plain

    @classmethod
    def verify(cls, conn: sqlite3.Connection, email: str, plain: str) -> bool:
        row = cls.find(conn, email.strip().lower())
        if not row:
            return False
        olusturma = datetime.fromisoformat(row.created_at)
        if olusturma + timedelta(minutes=TTL_MINUTES) < datetime.now(timezone.utc):
            return False
        return hmac.compare_digest(row.token, _hash(plain))

    @classmethod
    def consume(cls, conn: sqlite3.Connection, email: str) -> None:
        conn.execute("DELETE FROM password_reset_tokens WHERE email = ?", (email.strip().lower(),))
        conn.commit()
