"""
URL configuration for voicegen project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Django auth (login/logout)
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('voice_flow.urls')),
]

