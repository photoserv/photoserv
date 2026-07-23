import re
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import APIKey


class APIKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"
    auth_regex = re.compile(r"^Bearer ([A-Za-z0-9_\-\.~+/=]+)$")

    def authenticate(self, request):
        auth = request.headers.get("Authorization")
        if not auth:
            raise AuthenticationFailed("No API key provided.")

        match = self.auth_regex.match(auth)
        if not match:
            raise AuthenticationFailed("Invalid Authorization header format.")

        key = match.group(1)

        # Check all active API keys
        for api_key in APIKey.objects.filter(is_active=True):
            if api_key.check_key(key):
                return (None, api_key)  # valid key

        raise AuthenticationFailed("Invalid API key.")


    def authenticate_header(self, request):
        return "Authorization"
