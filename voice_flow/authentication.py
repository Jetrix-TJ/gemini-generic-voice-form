"""
Custom authentication for API keys
"""
from rest_framework import authentication
from rest_framework import exceptions
from .models import APIKey


class APIKeyUser:
    """
    A simple user-like object for API key authentication
    """
    def __init__(self, api_key):
        self.api_key = api_key
        self.is_authenticated = True
        self.is_active = True
    
    def __str__(self):
        return f"APIKeyUser({self.api_key.name})"


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    API Key based authentication.
    
    Clients should authenticate by passing the API key in the 'X-API-Key' header.
    """
    
    keyword = 'X-API-Key'
    
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        
        if not api_key:
            return None
        
        return self.authenticate_credentials(api_key)
    
    def authenticate_credentials(self, key):
        try:
            api_key = APIKey.objects.get(key=key, is_active=True)
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API key')
        
        # Mark API key as used
        api_key.mark_used()
        
        # Return a user-like object and the api_key
        return (APIKeyUser(api_key), api_key)
    
    def authenticate_header(self, request):
        return self.keyword

