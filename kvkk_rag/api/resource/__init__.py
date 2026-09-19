"""API kaynaklari (Laravel JsonResource): MVC'nin View katmani. Model/dataclass ->
JSON sozlugu donusumu burada; controller'lar ham modeli disari vermez."""
from .base import Resource
from .envanter_resource import EnvanterResource, FindingResource
from .rbac_resource import DepartmentResource, RoleResource, UserResource
from .source_resource import SourceResource

__all__ = ["Resource", "EnvanterResource", "FindingResource", "DepartmentResource",
           "RoleResource", "UserResource", "SourceResource"]
