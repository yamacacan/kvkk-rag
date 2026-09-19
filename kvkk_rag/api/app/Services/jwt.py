"""JWT (HS256) erisim jetonu — stdlib ile, dis bagimlilik yok (tymon/jwt-auth karsiligi).

Erisim jetonu kisa omurlu ve durumsuzdur; cikista `jti` kara listeye (versiyonlu
onbellek deposu, kalan omur kadar TTL) yazilir. Yenileme jetonu opak ve DB'de
ozetli tutulur (PersonalAccessToken, name='refresh'); kullanildikca dondurulur.

Gizli anahtar: KVKK_JWT_SECRET; verilmemisse ilk calistirmada uretilip
app_keys tablosuna yazilir (coklu worker ayni anahtari gorsun diye)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from typing import Any

from . import permission_cache

ISSUER = "kvkk-rag"
ALGO = "HS256"
ACCESS_TTL_MINUTES = int(os.getenv("KVKK_JWT_TTL_MINUTES", "60"))
REFRESH_TTL_HOURS = int(os.getenv("KVKK_REFRESH_TTL_HOURS", "168"))  # 7 gun
BLACKLIST_PREFIX = "jwt_blacklist_"

_secret_cache: str | None = None


class JwtError(Exception):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def encode(payload: dict[str, Any], secret: str) -> str:
    header = _b64(json.dumps({"alg": ALGO, "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    imza = hmac.new(secret.encode("utf-8"), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(imza)}"


def decode(token: str, secret: str, verify_exp: bool = True) -> dict[str, Any]:
    try:
        header, body, imza = token.split(".")
    except ValueError:
        raise JwtError("Jeton biçimi geçersiz.")
    beklenen = hmac.new(secret.encode("utf-8"), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_unb64(imza), beklenen):
        raise JwtError("Jeton imzası geçersiz.")
    try:
        bas = json.loads(_unb64(header))
        payload = json.loads(_unb64(body))
    except (ValueError, UnicodeDecodeError):
        raise JwtError("Jeton içeriği çözülemedi.")
    if bas.get("alg") != ALGO:
        raise JwtError("Desteklenmeyen imza algoritması.")
    if verify_exp and payload.get("exp", 0) < int(time.time()):
        raise JwtError("Jetonun süresi dolmuş.")
    return payload


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


class JwtService:
    def __init__(self, cache: permission_cache.PermissionCache | None = None) -> None:
        self.cache = cache or permission_cache.cache

    # ---- gizli anahtar ----
    @staticmethod
    def secret(conn: sqlite3.Connection | None = None) -> str:
        global _secret_cache
        if _secret_cache:
            return _secret_cache
        env = os.getenv("KVKK_JWT_SECRET", "").strip()
        if env:
            _secret_cache = env
            return env
        if conn is None:
            raise JwtError("KVKK_JWT_SECRET tanımlı değil ve veritabanı bağlantısı yok.")
        conn.execute("CREATE TABLE IF NOT EXISTS app_keys (name TEXT PRIMARY KEY, value TEXT NOT NULL, created_at TEXT NOT NULL)")
        r = conn.execute("SELECT value FROM app_keys WHERE name = 'jwt_secret'").fetchone()
        if r:
            _secret_cache = r[0]
            return r[0]
        yeni = secrets.token_urlsafe(48)
        conn.execute("INSERT OR IGNORE INTO app_keys (name, value, created_at) VALUES ('jwt_secret', ?, ?)",
                     (yeni, time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())))
        conn.commit()
        # Yaris durumunda baska worker once yazmis olabilir; DB'dekini esas al
        _secret_cache = conn.execute("SELECT value FROM app_keys WHERE name = 'jwt_secret'").fetchone()[0]
        return _secret_cache

    @staticmethod
    def forget_secret() -> None:
        global _secret_cache
        _secret_cache = None

    # ---- uretim / dogrulama ----
    def issue_access(self, conn: sqlite3.Connection, user: Any, ttl_minutes: int | None = None,
                     sid: int | None = None) -> tuple[str, dict[str, Any]]:
        # sid: bagli yenileme jetonunun (oturumun) kimligi; "aktif oturumlar" ekrani icin
        simdi = int(time.time())
        payload = {
            "iss": ISSUER,
            "sub": str(user.id),
            "email": user.email,
            "name": user.name,
            "roles": user.role_names(conn),
            "typ": "access",
            "sid": sid,
            "jti": uuid.uuid4().hex,
            "iat": simdi,
            "exp": simdi + 60 * (ttl_minutes or ACCESS_TTL_MINUTES),
        }
        return encode(payload, self.secret(conn)), payload

    def verify(self, conn: sqlite3.Connection, token: str) -> dict[str, Any]:
        payload = decode(token, self.secret(conn))
        if payload.get("iss") != ISSUER or payload.get("typ") != "access":
            raise JwtError("Jeton bu uygulama için üretilmemiş.")
        if self.is_blacklisted(payload.get("jti", "")):
            raise JwtError("Jeton iptal edilmiş (çıkış yapılmış).")
        return payload

    # ---- kara liste ----
    def blacklist(self, jti: str, exp: int) -> None:
        kalan = max(1, int(exp) - int(time.time()))
        self.cache.put(BLACKLIST_PREFIX + jti, 1, ttl=kalan)

    def is_blacklisted(self, jti: str) -> bool:
        return bool(jti) and self.cache.get(BLACKLIST_PREFIX + jti) is not None
