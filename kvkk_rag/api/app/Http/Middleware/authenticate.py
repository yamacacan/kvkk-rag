"""auth:api karsiligi. `Authorization: Bearer ...` basligi:
  - JWT (uc parca) -> imza, omur, kara liste dogrulanir (durumsuz)
  - "{id}|{gizli}" -> Sanctum tarzi API anahtari (DB)
Kullanici request.state.user, JWT iddialari request.state.jwt olarak baglanir."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ....database.connection import get_db
from ...Models.user import User
from ...Services.auth_service import AuthService

bearer = HTTPBearer(auto_error=False, description="Giriş: POST /api/auth/login (JWT)")


def optional_user(request: Request,
                  credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                  conn: sqlite3.Connection = Depends(get_db)) -> User | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    user, claims = AuthService.user_from_bearer(conn, credentials.credentials)
    request.state.user = user
    request.state.jwt = claims
    request.state.token = credentials.credentials if user else None
    return user


def authenticate(request: Request, user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=401, detail="Oturum açmanız gerekiyor.",
            headers={"WWW-Authenticate": "Bearer"})
    return user


# Laravel'deki auth()->user() / $request->user() okunusu
current_user = authenticate
