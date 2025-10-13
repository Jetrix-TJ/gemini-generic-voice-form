"""
URL routing for Voice Flow app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# API Router
router = DefaultRouter()
router.register(r'forms', views.VoiceFormConfigViewSet, basename='voiceform')
router.register(r'sessions', views.MagicLinkSessionViewSet, basename='session')
router.register(r'api-keys', views.APIKeyViewSet, basename='apikey')

urlpatterns = [
    # Public pages
    path('', views.home, name='home'),
    path('f/<str:form_id>/', views.form_interface, name='form_interface'),
    path('s/<str:session_id>/', views.session_interface, name='session_interface'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # API endpoints
    path('api/', include(router.urls)),
]

