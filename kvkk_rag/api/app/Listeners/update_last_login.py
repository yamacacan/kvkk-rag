from __future__ import annotations

from ..Events import Login
from ..Models.base import now


class UpdateLastLogin:
    def handle(self, event: Login) -> None:
        event.user.update(event.conn, last_login_at=now())
