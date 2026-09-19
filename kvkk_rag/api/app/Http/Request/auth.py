from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)
    device: str = "web"


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3)

    @field_validator("email")
    @classmethod
    def _eposta(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return v


class ResetPasswordRequest(BaseModel):
    email: str = Field(min_length=3)
    token: str = Field(min_length=10)
    password: str = Field(min_length=8)
    password_confirmation: str

    @model_validator(mode="after")
    def _eslesme(self) -> "ResetPasswordRequest":
        if self.password != self.password_confirmation:
            raise ValueError("Şifre tekrarı eşleşmiyor.")
        return self


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2)
    email: str | None = None

    @field_validator("email")
    @classmethod
    def _eposta(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    password: str = Field(min_length=8)
    password_confirmation: str

    @model_validator(mode="after")
    def _eslesme(self) -> "PasswordChangeRequest":
        if self.password != self.password_confirmation:
            raise ValueError("Şifre tekrarı eşleşmiyor.")
        if self.password == self.current_password:
            raise ValueError("Yeni şifre mevcut şifreyle aynı olamaz.")
        return self
