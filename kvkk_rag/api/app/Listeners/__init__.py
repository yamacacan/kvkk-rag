"""Olay -> dinleyici eslemesi (Laravel EventServiceProvider::$listen)."""
from __future__ import annotations

from ..Events import (ConsentChanged, DocumentFailed, DocumentGenerated, DocumentRequested, EnvanterChanged,
                      EnvanterIslemiBasarisiz, EnvanterIslemiTamamlandi, FaaliyetBelgesiYenilendi, JobFailed,
                      KurumProfiliGuncellendi, Login, Logout, PageViewed, PasswordReset, PermissionsChanged, listen)
from .handle_job_failure import HandleJobFailure
from .log_consent_change import LogConsentChange
from .log_document_activity import LogDocumentActivity
from .log_faaliyet_belgesi import LogFaaliyetBelgesi
from .log_envanter_change import LogEnvanterChange
from .log_logout import LogLogout
from .log_page_view import LogPageView
from .log_permission_change import LogPermissionChange
from .notify_document_owner import NotifyDocumentOwner
from .notify_envanter_islemi import NotifyEnvanterIslemi
from .refresh_faaliyet_belgeleri import RefreshFaaliyetBelgeleri
from .revoke_sessions_on_password_reset import RevokeSessionsOnPasswordReset
from .update_last_login import UpdateLastLogin


def register() -> None:
    # kimlik / yetki
    listen(Login, UpdateLastLogin())
    listen(Logout, LogLogout())
    listen(PermissionsChanged, LogPermissionChange())
    listen(PasswordReset, RevokeSessionsOnPasswordReset())
    # envanter: her veri girisi / aktarimi denetim gunlugune; kuyruk isleri bitince bildirim
    listen(EnvanterChanged, LogEnvanterChange())
    listen(EnvanterIslemiTamamlandi, NotifyEnvanterIslemi())
    listen(EnvanterIslemiBasarisiz, NotifyEnvanterIslemi())
    # faaliyet belgeleri: envanter/profil degisince otomatik yenilenir; sonucu gunluge
    listen(EnvanterChanged, RefreshFaaliyetBelgeleri())
    listen(KurumProfiliGuncellendi, RefreshFaaliyetBelgeleri())
    listen(FaaliyetBelgesiYenilendi, LogFaaliyetBelgesi())
    # acik riza kayitlari
    listen(ConsentChanged, LogConsentChange())
    # belgeler: istek/uretim/hata gunluge; hazir/hata bildirimi kullaniciya
    listen(DocumentRequested, LogDocumentActivity())
    listen(DocumentGenerated, LogDocumentActivity())
    listen(DocumentFailed, LogDocumentActivity())
    listen(DocumentGenerated, NotifyDocumentOwner())
    listen(DocumentFailed, NotifyDocumentOwner())
    # kuyruk / arayuz
    listen(JobFailed, HandleJobFailure())
    listen(PageViewed, LogPageView())
