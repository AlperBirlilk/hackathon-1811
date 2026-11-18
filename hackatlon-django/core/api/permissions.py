from rest_framework.permissions import BasePermission

from core.models import PermissionType


class HasDataAccess(BasePermission):
    message = 'Bu API için Veri Erişimi (DATA_ACCESS) yetkisi gerekiyor.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_portal_perm(PermissionType.DATA_ACCESS))


class HasRoleManagement(BasePermission):
    message = 'Ekip bilgisini görüntülemek için Rol Yönetimi (ROLE_MANAGEMENT) yetkisi gerekiyor.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.has_portal_perm(PermissionType.ROLE_MANAGEMENT))
