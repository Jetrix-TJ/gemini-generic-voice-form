"""
ASGI config for voicegen project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "voicegen.settings")

# Initialize Django ASGI application early to ensure Django is setup
# before importing models and routing
django_asgi_app = get_asgi_application()

# Now import routing after Django is initialized
import voice_flow.routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(voice_flow.routing.websocket_urlpatterns),
    }
)
