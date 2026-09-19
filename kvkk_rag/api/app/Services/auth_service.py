"""Kimlik dogrulama.

Giris      -> access JWT (kisa omur, durumsuz) + refresh jetonu (opak, DB, dondurulur)
Yenileme   -> refresh jetonu dogrulanir, eski silinir, yeni cift verilir
Cikis      -> access `jti` kara listeye, refresh jetonu silinir
Bearer     -> JWT ise imza/omur/kara liste; degilse Sanctum tarzi API anahtari
Sifre      -> forgot: e-postaya tek kullanimlik baglanti (Job ile), reset: jeton dogrula,
              sifreyi degistir, tum oturumlari dusur (PasswordReset olayi)."""
from __future__ import annotations

import os
import sqlite3
from typing import Any
from urllib.parse import quote

from fastapi import BackgroundTasks

from ..Events import Login, PasswordReset, PasswordResetRequested, dispatch
from ..Jobs.send_password_reset_mail_job import SendPasswordResetMailJob
from ..Models.audit_log import AuditLog
from ..Models.password_reset_token import TTL_MINUTES as RESET_TTL_MINUTES
from ..Models.password_reset_token import PasswordResetToken
from ..Models.personal_access_token import PersonalAccessToken
from ..Models.user import User
from . import jwt as jwt_service
from .jwt import JwtError, JwtService
from .mail_service import mailer

REFRESH_NAME = "refresh"
APP_URL = os.getenv("KVKK_APP_URL", "http://localhost:8000").rstrip("/")
APP_ENV = os.getenv("KVKK_APP_ENV", "local").strip().lower()


class AuthError(Exception):
    pass


def is_local() -> bool:
    return APP_ENV in ("local", "development", "dev", "testing")


class AuthService:
    jwt = JwtService()

    # ---- giris / jeton ----
    @staticmethod
    def attempt(conn: sqlite3.Connection, email: str, password: str) -> User | None:
        user = User.find_by_email(conn, email)
        if not user or not user.active or not user.check_password(password):
            return None
        return user

    @classmethod
    def tokens_for(cls, conn: sqlite3.Connection, user: User, device: str = "web") -> dict[str, Any]:
        # once yenileme jetonu (oturum kaydi), sonra ona bagli access JWT (sid)
        oturum, refresh = PersonalAccessToken.issue(conn, user.id, name=REFRESH_NAME,
                                                    ttl_hours=jwt_service.REFRESH_TTL_HOURS,
                                                    abilities=f"refresh:{device}")
        access, payload = cls.jwt.issue_access(conn, user, sid=oturum.id)
        return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer",
                "expires_in": jwt_service.ACCESS_TTL_MINUTES * 60, "expires_at": payload["exp"],
                "session_id": oturum.id}

    @classmethod
    def login(cls, conn: sqlite3.Connection, email: str, password: str,
              device: str = "web", ip: str | None = None) -> tuple[User, dict[str, Any]]:
        user = cls.attempt(conn, email, password)
        if not user:
            AuditLog.record(conn, "auth.login_failed", target_type="User",
                            target_label=email.strip().lower(), ip=ip)
            raise AuthError("E-posta veya şifre hatalı.")
        tokens = cls.tokens_for(conn, user, device)
        dispatch(Login(user=user, conn=conn))
        AuditLog.record(conn, "auth.login", actor=user, target=user, after={"device": device}, ip=ip)
        return user, tokens

    # ---- oturumlar ----
    @staticmethod
    def sessions(conn: sqlite3.Connection, user: User, current_sid: int | None = None) -> list[dict[str, Any]]:
        out = []
        for t in (PersonalAccessToken.query(conn).where("tokenable_type", "User")
                  .where("tokenable_id", user.id).where("name", REFRESH_NAME).order_by("id", "DESC").get()):
            out.append({"id": t.id, "cihaz": (t.abilities or "refresh:web").split(":", 1)[-1],
                        "olusturma": t.created_at, "son_kullanim": t.last_used_at,
                        "bitis": t.expires_at, "mevcut": t.id == current_sid})
        return out

    @staticmethod
    def revoke_session(conn: sqlite3.Connection, user: User, session_id: int) -> bool:
        t = PersonalAccessToken.find(conn, session_id)
        if not t or t.tokenable_id != user.id or t.name != REFRESH_NAME:
            return False
        return t.delete(conn)

    @staticmethod
    def revoke_other_sessions(conn: sqlite3.Connection, user: User, keep_sid: int | None) -> int:
        q = (PersonalAccessToken.query(conn).where("tokenable_type", "User")
             .where("tokenable_id", user.id).where("name", REFRESH_NAME))
        if keep_sid:
            q.where("id", "!=", keep_sid)
        return q.delete()

    # ---- profil ----
    @classmethod
    def update_profile(cls, conn: sqlite3.Connection, user: User, name: str | None,
                       email: str | None, ip: str | None = None) -> User:
        degisiklik: dict[str, Any] = {}
        if name is not None and name.strip() and name.strip() != user.name:
            degisiklik["name"] = name.strip()
        if email is not None and email.strip().lower() != user.email:
            mevcut = User.find_by_email(conn, email)
            if mevcut and mevcut.id != user.id:
                raise AuthError("Bu e-posta başka bir hesapta kayıtlı.")
            degisiklik["email"] = email.strip().lower()
        if degisiklik:
            once = {k: user.get(k) for k in degisiklik}
            user.update(conn, **degisiklik)
            AuditLog.record(conn, "auth.profile_update", actor=user, target=user,
                            before=once, after=degisiklik, ip=ip)
        return user

    @classmethod
    def change_password(cls, conn: sqlite3.Connection, user: User, current: str, new: str,
                        keep_sid: int | None = None, ip: str | None = None) -> int:
        if not user.check_password(current):
            raise AuthError("Mevcut şifre hatalı.")
        user.set_password(conn, new)
        n = cls.revoke_other_sessions(conn, user, keep_sid)  # diger cihazlar dusurulur
        AuditLog.record(conn, "auth.password_change", actor=user, target=user,
                        after={"iptal_edilen_oturum": n}, ip=ip)
        return n

    @classmethod
    def refresh(cls, conn: sqlite3.Connection, refresh_plain: str) -> tuple[User, dict[str, Any]]:
        token = PersonalAccessToken.find_token(conn, refresh_plain)
        if not token or token.name != REFRESH_NAME:
            raise AuthError("Yenileme jetonu geçersiz veya süresi dolmuş.")
        user = User.find(conn, token.tokenable_id)
        if not user or not user.active:
            raise AuthError("Hesap bulunamadı veya pasif.")
        device = (token.abilities or "refresh:web").split(":", 1)[-1]
        token.delete(conn)  # dondurme: eski yenileme jetonu tek kullanimlik
        return user, cls.tokens_for(conn, user, device)

    @classmethod
    def logout(cls, conn: sqlite3.Connection, claims: dict[str, Any] | None,
               refresh_plain: str | None = None) -> bool:
        if claims and claims.get("jti"):
            cls.jwt.blacklist(claims["jti"], int(claims.get("exp", 0)))
        if refresh_plain:
            PersonalAccessToken.revoke(conn, refresh_plain)
        return True

    @staticmethod
    def logout_everywhere(conn: sqlite3.Connection, user: User) -> int:
        return PersonalAccessToken.revoke_all(conn, user.id)

    @classmethod
    def user_from_bearer(cls, conn: sqlite3.Connection, bearer: str) -> tuple[User | None, dict[str, Any] | None]:
        """-> (kullanici, jwt_claims|None). JWT ise durumsuz dogrulama; degilse API anahtari."""
        if jwt_service.looks_like_jwt(bearer):
            try:
                claims = cls.jwt.verify(conn, bearer)
            except JwtError:
                return None, None
            user = User.find(conn, int(claims["sub"]))
            if not user or not user.active:
                return None, None
            return user, claims
        token = PersonalAccessToken.find_token(conn, bearer)
        if not token or token.name == REFRESH_NAME:  # yenileme jetonu erisim icin kullanilamaz
            return None, None
        user = User.find(conn, token.tokenable_id)
        if not user or not user.active:
            return None, None
        token.touch(conn)
        return user, None

    # ---- sifre sifirlama ----
    @staticmethod
    def reset_url(email: str, plain_token: str) -> str:
        return f"{APP_URL}/sifre-sifirla?token={quote(plain_token)}&email={quote(email)}"

    @classmethod
    def send_reset_link(cls, conn: sqlite3.Connection, email: str,
                        background: BackgroundTasks | None = None) -> str | None:
        """Kullanici yoksa da sessizce doner (hesap sayimini engeller). Gelistirmede
        (APP_ENV=local, MAIL_DRIVER=log) baglantiyi dondurur ki akis denenebilsin."""
        user = User.find_by_email(conn, email)
        if not user or not user.active:
            return None
        plain = PasswordResetToken.issue(conn, user.email)
        url = cls.reset_url(user.email, plain)
        SendPasswordResetMailJob(user.email, user.name, url, RESET_TTL_MINUTES).dispatch(background)
        dispatch(PasswordResetRequested(user=user, reset_url=url))
        return url if (is_local() and mailer.driver == "log") else None

    @classmethod
    def reset_password(cls, conn: sqlite3.Connection, email: str, token: str, password: str) -> User:
        user = User.find_by_email(conn, email)
        if not user or not PasswordResetToken.verify(conn, email, token):
            raise AuthError("Şifre sıfırlama bağlantısı geçersiz veya süresi dolmuş.")
        user.set_password(conn, password)
        PasswordResetToken.consume(conn, email)
        dispatch(PasswordReset(user=user, conn=conn))
        AuditLog.record(conn, "auth.password_reset", actor=user, target=user)
        return user
