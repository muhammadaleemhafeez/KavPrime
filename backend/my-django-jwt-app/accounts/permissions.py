from rest_framework.permissions import BasePermission

class IsAuthenticated(BasePermission):
    """
    Custom permission to only allow authenticated users to access certain views.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

class IsOwner(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user