from __future__ import annotations

import sqlite3

from ..Events import PermissionsChanged, dispatch
from ..Services.permission_cache import flush_cache


class PermissionScopeObserver:
    """permission_scopes satiri yazildiginda/silindiginde: O(1) gecersizleme."""

    def saved(self, scope, conn: sqlite3.Connection) -> None:
        v = flush_cache()
        dispatch(PermissionsChanged(reason=f"kapsam: rol {scope.role_id} {scope.module}.{scope.action}={scope.scope}",
                                    version=v))

    def deleted(self, scope, conn: sqlite3.Connection) -> None:
        v = flush_cache()
        dispatch(PermissionsChanged(reason=f"kapsam silindi: rol {scope.role_id} {scope.module}.{scope.action}",
                                    version=v))
