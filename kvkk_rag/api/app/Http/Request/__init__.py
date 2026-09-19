"""Istek dogrulama modelleri (Laravel FormRequest karsiligi, Pydantic).
Her modul kendi dosyasinda; burada disa aktarilir."""
from .auth import (ForgotPasswordRequest, LoginRequest, LogoutRequest, PasswordChangeRequest,
                   ProfileUpdateRequest, RefreshRequest, ResetPasswordRequest)
from .chat import AskRequest, ChatMessage, ChatRequest
from .document import DocumentRequest, ProfileRequest
from .inventory import (AssignRequest, BulkDeleteRequest, InventorySearchRequest,
                        RowPayload, SuggestRequest)
from .rbac import (DepartmentRequest, RoleStoreRequest, RoleUpdateRequest, ScopeItem,
                   ScopeSyncRequest, UserStoreRequest, UserUpdateRequest)

__all__ = [
    "LoginRequest", "RefreshRequest", "LogoutRequest", "ForgotPasswordRequest", "ResetPasswordRequest", "AskRequest", "ChatMessage", "ChatRequest", "DocumentRequest",
    "ProfileRequest", "AssignRequest", "BulkDeleteRequest", "InventorySearchRequest",
    "RowPayload", "SuggestRequest", "DepartmentRequest", "RoleStoreRequest",
    "RoleUpdateRequest", "ScopeItem", "ScopeSyncRequest", "UserStoreRequest", "UserUpdateRequest",
]
