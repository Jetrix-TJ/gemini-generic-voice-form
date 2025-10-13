"""
WebSocket URL routing
"""
from django.urls import re_path
from . import consumers
from . import live_consumer

websocket_urlpatterns = [
    # Live API bidirectional audio (Gemini 2.5 Flash Native Audio)
    re_path(r'ws/live/(?P<session_id>[^/]+)/$', live_consumer.LiveAudioConsumer.as_asgi())
]

