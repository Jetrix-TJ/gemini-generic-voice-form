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
    path('create-form/', views.create_form_page, name='create_form_page'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/forms/<str:form_id>/', views.form_detail, name='form_detail'),
    path('dashboard/forms/<str:form_id>/export.csv', views.export_form_csv, name='export_form_csv'),
    path('accounts/signup/', views.signup, name='signup'),
    path('dashboard/link-api-key/', views.link_api_key, name='link_api_key'),
    path('dashboard/create-api-key/', views.create_linked_api_key, name='create_linked_api_key'),
    path('api/generate-form-schema/', views.generate_form_schema, name='generate_form_schema'),
    path('dev/create-api-key/', views.dev_create_api_key, name='dev_create_api_key'),
    path('f/<str:form_id>/', views.form_interface, name='form_interface'),
    path('s/<str:session_id>/finalize/', views.finalize_session_public, name='finalize_session_public'),
    path('s/<str:session_id>/', views.session_interface, name='session_interface'),
    
    # Health check
    path('health/', views.health_check, name='health_check'),
    
    # API endpoints
    path('api/', include(router.urls)),
]

