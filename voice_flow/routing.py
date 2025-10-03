from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/voice/(?P<session_id>[a-f0-9\-]+)/$",
        consumers.VoiceConsumer.as_asgi(),
    ),
]
