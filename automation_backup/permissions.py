# automation/permissions.py
from rest_framework import permissions

class IsAdminOrAmbassadorForDestination(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin():
            return True
        if request.user.is_ambassador() and obj.city == request.user.destination:
            return True
        return False
