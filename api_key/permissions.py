from rest_framework.permissions import BasePermission


class IsAuthenticatedOrHasAPIKey(BasePermission):
    """
    Allows access if APIKeyAuthentication succeeded, even if request.user is None.
    """
    def has_permission(self, request, view):
        writing = request.method not in ('GET', 'HEAD', 'OPTIONS')
        return bool(
            request.user and request.user.is_authenticated
        ) or (
            request.auth is not None and (not writing or request.auth.write_access)
        )
