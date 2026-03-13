from datetime import timedelta
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone

def create_jwt_token(user):
    refresh = RefreshToken.for_user(user)
    access = AccessToken.for_user(user)
    access.set_exp(lifetime=timedelta(days=7))
    return {
        'refresh': str(refresh),
        'access': str(access),
    }

class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth = super().authenticate(request)
        if auth is None:
            raise AuthenticationFailed('Invalid token')
        return auth

def validate_jwt_token(token):
    try:
        validated_token = AccessToken(token)
        return validated_token
    except Exception:
        return None