"""Kimlik uclari: JWT giris / yenileme / cikis, ben, profil, sifre, oturumlar,
sifremi unuttum, sifre sifirla."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import BackgroundTasks, Depends, HTTPException, Request

from ....database.connection import get_db
from ....resource import UserResource
from ...Events import Logout, dispatch
from ...Models.user import User
from ...Services.auth_service import AuthError, AuthService
from ..Middleware.authenticate import authenticate
from ..Request.auth import (ForgotPasswordRequest, LoginRequest, LogoutRequest,
                            PasswordChangeRequest, ProfileUpdateRequest, RefreshRequest,
                            ResetPasswordRequest)
from .base import Controller, route

GENEL_MESAJ = "Bu e-posta kayıtlıysa şifre sıfırlama bağlantısı gönderildi."


def _ip(request: Request) -> str | None:
    ileri = request.headers.get("x-forwarded-for")
    if ileri:
        return ileri.split(",")[0].strip()
    return request.client.host if request.client else None


def _sid(request: Request) -> int | None:
    claims = getattr(request.state, "jwt", None) or {}
    return claims.get("sid")


class AuthController(Controller):
    prefix = "/api/auth"
    tags = ["auth"]

    @route("POST", "/login")
    def login(self, req: LoginRequest, request: Request,
              conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        try:
            user, tokens = AuthService.login(conn, req.email, req.password, device=req.device, ip=_ip(request))
        except AuthError as e:
            raise HTTPException(401, str(e))
        return {**tokens, "user": UserResource.make(user, conn=conn, detailed=True)}

    @route("POST", "/refresh")
    def refresh(self, req: RefreshRequest, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        try:
            user, tokens = AuthService.refresh(conn, req.refresh_token)
        except AuthError as e:
            raise HTTPException(401, str(e))
        return {**tokens, "user": UserResource.make(user, conn=conn, detailed=True)}

    @route("POST", "/logout")
    def logout(self, request: Request, req: LogoutRequest | None = None,
               user: User = Depends(authenticate),
               conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # JWT jti kara listeye; bagli oturum (sid) ve verildiyse refresh jetonu silinir
        AuthService.logout(conn, getattr(request.state, "jwt", None), req.refresh_token if req else None)
        if _sid(request):
            AuthService.revoke_session(conn, user, _sid(request))
        dispatch(Logout(user=user, conn=conn, ip=_ip(request)))
        return {"cikis": True}

    @route("POST", "/logout-all")
    def logout_all(self, request: Request, user: User = Depends(authenticate),
                   conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        AuthService.logout(conn, getattr(request.state, "jwt", None))
        n = AuthService.logout_everywhere(conn, user)
        dispatch(Logout(user=user, conn=conn, ip=_ip(request)))
        return {"iptal_edilen_oturum": n}

    @route("GET", "/me")
    def me(self, user: User = Depends(authenticate),
           conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # roller, izinler ve cozumlenmis kapsam matrisi: arayuz neyi gosterecegini bilir
        return {"user": UserResource.make(user, conn=conn, detailed=True)}

    # ---- profil (kendi hesabi) ----
    @route("PATCH", "/profile")
    def update_profile(self, req: ProfileUpdateRequest, request: Request,
                       user: User = Depends(authenticate),
                       conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        try:
            AuthService.update_profile(conn, user, req.name, req.email, ip=_ip(request))
        except AuthError as e:
            raise HTTPException(422, str(e))
        return {"user": UserResource.make(user, conn=conn, detailed=True)}

    @route("POST", "/password")
    def change_password(self, req: PasswordChangeRequest, request: Request,
                        user: User = Depends(authenticate),
                        conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        try:
            n = AuthService.change_password(conn, user, req.current_password, req.password,
                                            keep_sid=_sid(request), ip=_ip(request))
        except AuthError as e:
            raise HTTPException(422, str(e))
        return {"mesaj": "Şifreniz güncellendi.", "iptal_edilen_oturum": n}

    @route("GET", "/sessions")
    def sessions(self, request: Request, user: User = Depends(authenticate),
                 conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"oturumlar": AuthService.sessions(conn, user, _sid(request))}

    @route("DELETE", "/sessions/{session_id}")
    def revoke_session(self, session_id: int, user: User = Depends(authenticate),
                       conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        if not AuthService.revoke_session(conn, user, session_id):
            raise HTTPException(404, "Oturum bulunamadı")
        return {"iptal": session_id}

    @route("POST", "/sessions/revoke-others")
    def revoke_others(self, request: Request, user: User = Depends(authenticate),
                      conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        return {"iptal_edilen_oturum": AuthService.revoke_other_sessions(conn, user, _sid(request))}

    # ---- sifre sifirlama ----
    @route("POST", "/forgot-password")
    def forgot_password(self, req: ForgotPasswordRequest, background: BackgroundTasks,
                        conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        # Hesap olsa da olmasa da ayni yanit: e-posta sayimi yapilamaz
        url = AuthService.send_reset_link(conn, req.email, background)
        out: dict[str, Any] = {"mesaj": GENEL_MESAJ}
        if url:
            # yalnizca gelistirme (APP_ENV=local + MAIL_DRIVER=log): e-posta yerine burada
            out["gelistirme"] = {"reset_url": url, "not": "MAIL_DRIVER=log; bağlantı günlüğe de yazıldı"}
        return out

    @route("POST", "/reset-password")
    def reset_password(self, req: ResetPasswordRequest,
                       conn: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
        try:
            user = AuthService.reset_password(conn, req.email, req.token, req.password)
        except AuthError as e:
            raise HTTPException(422, str(e))
        return {"mesaj": "Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.", "email": user.email}
