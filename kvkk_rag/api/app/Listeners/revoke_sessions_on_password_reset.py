from __future__ import annotations

import logging

from ..Events import PasswordReset
from ..Models.personal_access_token import PersonalAccessToken

logger = logging.getLogger("kvkk_rag.api.auth")


class RevokeSessionsOnPasswordReset:
    # Sifre degisince acik tum oturumlar (yenileme jetonlari) dusurulur
    def handle(self, event: PasswordReset) -> None:
        n = PersonalAccessToken.revoke_all(event.conn, event.user.id)
        logger.info("Şifre sıfırlandı: %s (%s oturum iptal)", event.user.email, n)
