"""Sifre ozeti (Laravel Hash facade). Dis bagimlilik gerektirmesin diye stdlib
PBKDF2-HMAC-SHA256; bicim: pbkdf2_sha256$<tur>$<tuz>$<ozet>."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

ALGO = "pbkdf2_sha256"
ITERATIONS = 600_000  # OWASP 2023 onerisi; testler dusurebilir


def make(password: str, iterations: int | None = None) -> str:
    tur = iterations or ITERATIONS
    tuz = base64.b64encode(os.urandom(16)).decode("ascii")
    ozet = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), tuz.encode("ascii"), tur)
    return f"{ALGO}${tur}${tuz}${base64.b64encode(ozet).decode('ascii')}"


def check(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        algo, tur, tuz, ozet = hashed.split("$", 3)
        if algo != ALGO:
            return False
        aday = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), tuz.encode("ascii"), int(tur))
        return hmac.compare_digest(base64.b64encode(aday).decode("ascii"), ozet)
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        algo, tur, _, _ = hashed.split("$", 3)
        return algo != ALGO or int(tur) != ITERATIONS
    except ValueError:
        return True
