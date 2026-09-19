"""Sanctum tarzi kisisel erisim jetonu. Duz metin jeton yalnizca girişte bir kez
verilir; tabloda SHA-256 ozeti tutulur. Bicim: "{id}|{rastgele}"."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .base import Model, now


def _hash(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class PersonalAccessToken(Model):
    table = "personal_access_tokens"
    fillable = ("tokenable_type", "tokenable_id", "name", "token", "abilities",
                "last_used_at", "expires_at")

    @classmethod
    def issue(cls, conn: sqlite3.Connection, user_id: int, name: str = "api",
              ttl_hours: int | None = 24, abilities: str = "*") -> tuple["PersonalAccessToken", str]:
        rastgele = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat(timespec="seconds") \
            if ttl_hours else None
        token = cls.create(conn, tokenable_type="User", tokenable_id=user_id, name=name,
                           token=_hash(rastgele), abilities=abilities, expires_at=expires)
        return token, f"{token.id}|{rastgele}"

    @classmethod
    def find_token(cls, conn: sqlite3.Connection, plain: str) -> "PersonalAccessToken | None":
        # "{id}|{secret}" -> id ile tek satir okunur, ozet karsilastirilir
        if "|" not in plain:
            return None
        kimlik, gizli = plain.split("|", 1)
        if not kimlik.isdigit():
            return None
        t = cls.find(conn, int(kimlik))
        if not t or t.token != _hash(gizli):
            return None
        if t.expires_at and t.expires_at < now():
            return None
        return t

    def touch(self, conn: sqlite3.Connection) -> None:
        # Her istekte yazmamak icin dakikada bir guncellenir
        son = self.last_used_at or ""
        if son[:16] != now()[:16]:
            self.update(conn, last_used_at=now())

    @classmethod
    def revoke(cls, conn: sqlite3.Connection, plain: str) -> bool:
        t = cls.find_token(conn, plain)
        return bool(t and t.delete(conn))

    @classmethod
    def revoke_all(cls, conn: sqlite3.Connection, user_id: int) -> int:
        return cls.query(conn).where("tokenable_type", "User").where("tokenable_id", user_id).delete()
