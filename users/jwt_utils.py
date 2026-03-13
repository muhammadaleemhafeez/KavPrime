"""
JWT Utility Module
Handles token generation, decoding, and validation for the application.
"""
import jwt
import datetime
from django.conf import settings


def get_jwt_config():
    """Get JWT configuration from settings."""
    return settings.JWT_AUTH


def generate_token(user):
    """
    Generate a JWT access token for the given user.
    Token is valid for 7 days (configured in settings).
    """
    config = get_jwt_config()
    now = datetime.datetime.now(datetime.timezone.utc)

    payload = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role,
        'name': user.name,
        'iat': now,                                       # Issued at
        'exp': now + config['JWT_EXPIRATION_DELTA'],      # Expiration (7 days)
        'token_type': 'access',
    }

    token = jwt.encode(
        payload,
        config['JWT_SECRET_KEY'],
        algorithm=config['JWT_ALGORITHM']
    )

    return token


def generate_refresh_token(user):
    """
    Generate a JWT refresh token for the given user.
    Refresh token is valid for 14 days (double the access token).
    """
    config = get_jwt_config()
    now = datetime.datetime.now(datetime.timezone.utc)

    payload = {
        'user_id': user.id,
        'email': user.email,
        'iat': now,
        'exp': now + (config['JWT_EXPIRATION_DELTA'] * 2),  # 14 days
        'token_type': 'refresh',
    }

    token = jwt.encode(
        payload,
        config['JWT_SECRET_KEY'],
        algorithm=config['JWT_ALGORITHM']
    )

    return token


def decode_token(token):
    """
    Decode and validate a JWT token.
    Returns the payload if valid, raises exceptions otherwise.
    """
    config = get_jwt_config()

    try:
        payload = jwt.decode(
            token,
            config['JWT_SECRET_KEY'],
            algorithms=[config['JWT_ALGORITHM']]
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def get_token_from_request(request):
    """
    Extract the Bearer token from the Authorization header.
    Expected header format: Authorization: Bearer <token>
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')

    if not auth_header:
        return None

    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    return parts[1]


def validate_token(token):
    """
    Validate a token and return user info if valid.
    Returns a dict with 'valid' status and payload/error.
    """
    try:
        payload = decode_token(token)
        return {
            'valid': True,
            'payload': payload
        }
    except ValueError as e:
        return {
            'valid': False,
            'error': str(e)
        }
