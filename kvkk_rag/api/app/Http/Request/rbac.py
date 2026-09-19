from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ...Models import permission_scope as ps


class UserStoreRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    roles: list[str] = []
    department_id: int | None = None
    departments: list[int] = []
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = Field(default=None, min_length=8)
    roles: list[str] | None = None
    department_id: int | None = None
    departments: list[int] | None = None
    is_active: bool | None = None


class ScopeItem(BaseModel):
    module: str
    action: str
    scope: str

    @field_validator("scope")
    @classmethod
    def _gecerli(cls, v: str) -> str:
        if not ps.is_valid(v):
            raise ValueError(f"Kapsam {', '.join(ps.SCOPES)} değerlerinden biri olmalı")
        return v


class RoleStoreRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    permissions: list[str] = []
    scopes: list[ScopeItem] = []


class RoleUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None   # verilirse tam liste ile eslenir (sync)
    scopes: list[ScopeItem] | None = None  # verilirse tam liste ile eslenir (sync)


class ScopeSyncRequest(BaseModel):
    scopes: list[ScopeItem]


class DepartmentRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    users: list[int] | None = None   # verilirse uye listesi bu kumeyle eslenir


class RoleCloneRequest(BaseModel):
    name: str = Field(min_length=1)
