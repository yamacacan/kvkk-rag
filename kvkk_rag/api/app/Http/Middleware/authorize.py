"""Spatie middleware karsiliklari:
  permission("findings.view")            -> tek izin
  permission("findings.view|findings.create") veya permission("a", "b") -> herhangi biri (OR)
  role("Admin|Denetçi")                  -> rollerden biri
Kapsam (2. kademe) burada degil; controller icinde ScopeFilter / has_scoped_permission ile."""
from __future__ import annotations

import sqlite3
from typing import Callable

from fastapi import Depends, HTTPException

from ....database.connection import get_db
from ...Models.user import User
from .authenticate import authenticate


def _split(names: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for n in names:
        out.extend(p.strip() for p in n.split("|") if p.strip())
    return out


def permission(*names: str) -> Callable[..., User]:
    istenen = _split(names)

    def _dep(user: User = Depends(authenticate), conn: sqlite3.Connection = Depends(get_db)) -> User:
        if not user.can_any(conn, istenen):
            raise HTTPException(
                status_code=403,
                detail=f"Bu işlem için '{' veya '.join(istenen)}' yetkisi gerekiyor.")
        return user

    _dep.__name__ = f"permission[{'|'.join(istenen)}]"
    return _dep


def role(*names: str) -> Callable[..., User]:
    istenen = _split(names)

    def _dep(user: User = Depends(authenticate), conn: sqlite3.Connection = Depends(get_db)) -> User:
        if not user.has_role(conn, *istenen):
            raise HTTPException(
                status_code=403,
                detail=f"Bu işlem için '{' veya '.join(istenen)}' rolü gerekiyor.")
        return user

    _dep.__name__ = f"role[{'|'.join(istenen)}]"
    return _dep
