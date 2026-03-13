from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
import jwt
from django.conf import settings

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        if token is not None:
            try:
                token = token.split(' ')[1]  # Get the token part after "Bearer"
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                request.user_id = payload['user_id']  # Assuming user_id is in the token payload
            except jwt.ExpiredSignatureError:
                return JsonResponse({'error': 'Token has expired'}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({'error': 'Invalid token'}, status=401)
        else:
            request.user_id = None  # No token provided

    def process_response(self, request, response):
        return response