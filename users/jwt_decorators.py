"""
JWT Authentication Decorator
Use @jwt_required on any view that needs authentication.
"""
import functools
from django.http import JsonResponse
from .models import User
from .jwt_utils import get_token_from_request, decode_token


def jwt_required(view_func):
    """
    Decorator that enforces JWT authentication on a view.
    Adds `request.jwt_user` (User instance) and `request.jwt_payload` to the request.
    
    Usage:
        @jwt_required
        def my_protected_view(request):
            user = request.jwt_user  # Authenticated user
            ...
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        token = get_token_from_request(request)

        if not token:
            return JsonResponse({
                "error": "Authentication required",
                "detail": "Authorization header with Bearer token is missing"
            }, status=401)

        try:
            payload = decode_token(token)
        except ValueError as e:
            return JsonResponse({
                "error": "Invalid or expired token",
                "detail": str(e)
            }, status=401)

        # Ensure it's an access token
        if payload.get('token_type') != 'access':
            return JsonResponse({
                "error": "Invalid token type",
                "detail": "Expected an access token"
            }, status=401)

        # Fetch the user from DB
        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            return JsonResponse({
                "error": "User not found",
                "detail": "The user associated with this token no longer exists"
            }, status=401)

        # Check if user is still active
        if not user.is_active:
            return JsonResponse({
                "error": "Account is inactive",
                "detail": "This user account has been deactivated"
            }, status=403)

        # Attach user and payload to request
        request.jwt_user = user
        request.jwt_payload = payload

        return view_func(request, *args, **kwargs)

    return wrapper


def jwt_role_required(*allowed_roles):
    """
    Decorator that enforces JWT authentication AND role-based access.
    
    Usage:
        @jwt_role_required("ADMIN", "HR")
        def admin_only_view(request):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @jwt_required
        def wrapper(request, *args, **kwargs):
            user_role = request.jwt_user.role.upper()
            if user_role not in [r.upper() for r in allowed_roles]:
                return JsonResponse({
                    "error": "Forbidden",
                    "detail": f"This action requires one of these roles: {', '.join(allowed_roles)}"
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
