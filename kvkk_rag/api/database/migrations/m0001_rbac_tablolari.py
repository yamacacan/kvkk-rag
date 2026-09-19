"""RBAC tablolari. Adlar Spatie Laravel-Permission ile birebir (roles, permissions,
role_has_permissions, model_has_roles, model_has_permissions); kapsam katmani icin
permission_scopes, oturum icin Sanctum'un personal_access_tokens tablosu."""
from __future__ import annotations

import sqlite3

SQL = """
CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password      TEXT NOT NULL,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

-- Coklu departman iliskisi; users.department_id tekil (birincil) departmandir.
CREATE TABLE IF NOT EXISTS user_departments (
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, department_id)
);

CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    guard_name  TEXT NOT NULL DEFAULT 'api',
    description TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (name, guard_name)
);

-- name = "modul.aksiyon" (findings.view gibi); module/action ayri sutunda da tutulur
-- ki kapsam tablosuyla birlesim ucuz olsun.
CREATE TABLE IF NOT EXISTS permissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    guard_name  TEXT NOT NULL DEFAULT 'api',
    module      TEXT NOT NULL,
    action      TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE (name, guard_name)
);

CREATE TABLE IF NOT EXISTS role_has_permissions (
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    role_id       INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (permission_id, role_id)
);

CREATE TABLE IF NOT EXISTS model_has_roles (
    role_id    INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    model_type TEXT NOT NULL DEFAULT 'User',
    model_id   INTEGER NOT NULL,
    PRIMARY KEY (role_id, model_type, model_id)
);
CREATE INDEX IF NOT EXISTS idx_model_has_roles_model ON model_has_roles(model_type, model_id);

CREATE TABLE IF NOT EXISTS model_has_permissions (
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    model_type    TEXT NOT NULL DEFAULT 'User',
    model_id      INTEGER NOT NULL,
    PRIMARY KEY (permission_id, model_type, model_id)
);
CREATE INDEX IF NOT EXISTS idx_model_has_permissions_model ON model_has_permissions(model_type, model_id);

-- 2. kademe: (role_id, module, action) => scope
CREATE TABLE IF NOT EXISTS permission_scopes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id    INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    module     TEXT NOT NULL,
    action     TEXT NOT NULL,
    scope      TEXT NOT NULL CHECK (scope IN ('all', 'department', 'assigned', 'own', 'none')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (role_id, module, action)
);
CREATE INDEX IF NOT EXISTS idx_permission_scopes_lookup ON permission_scopes(module, action, role_id);

CREATE TABLE IF NOT EXISTS personal_access_tokens (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    tokenable_type TEXT NOT NULL DEFAULT 'User',
    tokenable_id   INTEGER NOT NULL,
    name           TEXT NOT NULL,
    token          TEXT NOT NULL UNIQUE,
    abilities      TEXT,
    last_used_at   TEXT,
    expires_at     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pat_tokenable ON personal_access_tokens(tokenable_type, tokenable_id);
"""


def up(conn: sqlite3.Connection) -> None:
    conn.executescript(SQL)
