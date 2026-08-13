from rest_framework.permissions import BasePermission

class IsOrgMember(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        org_id = getattr(obj, "org_id", None) or getattr(obj, "owner", None) and obj.owner.org_id
        return org_id == request.user.org_id

class IsOwnerOrCreator(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ("PUT", "PATCH"):
            return obj.created_by_id == request.user.id or request.user.role == "owner"
        return True
