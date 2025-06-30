from rest_framework import permissions 
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminUser(permissions.BasePermission):
    """
    Permission class to allow only admin users to access the view.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists())
        )

class IsAmbassadorUser(permissions.BasePermission):
    """
    Permission class to allow only ambassador users to access the view.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.roles.filter(role='AMBASSADOR').exists()
        )

class IsAdminOrAmbassador(permissions.BasePermission):
    """
    Permission class to allow both admin and ambassador users to access the view.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return bool(
            request.user.is_superuser or 
            request.user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists()
        )

class HasDestinationPermission(permissions.BasePermission):
    """
    Permission class to check if user has access to specific destination data.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists():
            return True
            
        if request.user.roles.filter(role='AMBASSADOR').exists():
            # Check if the object's destination is in user's assigned destinations
            return obj.destination in request.user.destinations.all()
            
        return False

class IsAuthenticatedOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is read-only.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated
    

