"""RBAC Permission classes for Lumera Backend & CMS."""
from rest_framework import permissions


class IsStaffMember(permissions.BasePermission):
    """Allows access only to active staff users."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        )


def HasPermission(permission_code: str):
    """Factory creating a DRF Permission class requiring a specific permission code."""

    class PermissionCheck(permissions.BasePermission):
        code = permission_code

        def has_permission(self, request, view):
            if not (
                request.user
                and request.user.is_authenticated
                and request.user.is_active
                and request.user.is_staff
            ):
                return False
            return request.user.has_perm_code(self.code)

    PermissionCheck.__name__ = f"HasPermission_{permission_code.replace('.', '_')}"
    return PermissionCheck
