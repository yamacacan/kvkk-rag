"""Controller kaydi. Sira onemli: FastAPI ilk eslesen rotayi calistirir."""
from .audit_controller import AuditLogController
from .consent_controller import ConsentController
from .auth_controller import AuthController
from .chat_controller import ChatController
from .dashboard_controller import DashboardController
from .document_controller import DocumentController, ProfileController
from .faaliyet_belge_controller import FaaliyetBelgeController
from .graph_controller import GraphController
from .health_controller import HealthController
from .inventory_controller import InventoryController
from .notification_controller import NotificationController
from .queue_controller import QueueController
from .rbac_controller import (DepartmentController, PermissionController, RoleController,
                              UserController)
from .taxonomy_controller import TaxonomyController

CONTROLLERS = [
    HealthController, AuthController, DashboardController, ChatController, InventoryController,
    TaxonomyController, ProfileController, DocumentController, GraphController,
    UserController, RoleController, PermissionController, DepartmentController, AuditLogController,
    NotificationController, QueueController, FaaliyetBelgeController, ConsentController,
]

__all__ = ["CONTROLLERS", "AuditLogController", "NotificationController", "QueueController", "FaaliyetBelgeController", "ConsentController", "DashboardController", "AuthController", "ChatController", "DocumentController",
           "ProfileController", "GraphController", "HealthController", "InventoryController",
           "DepartmentController", "PermissionController", "RoleController", "UserController",
           "TaxonomyController"]
