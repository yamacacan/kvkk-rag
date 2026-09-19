from __future__ import annotations

import logging

from ..Events import PermissionsChanged

logger = logging.getLogger("kvkk_rag.api.rbac")


class LogPermissionChange:
    def handle(self, event: PermissionsChanged) -> None:
        logger.info("Yetki onbellegi surumu -> %s (%s)", event.version, event.reason)
