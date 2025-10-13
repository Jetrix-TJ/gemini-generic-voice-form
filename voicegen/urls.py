"""
URL configuration for voicegen project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('voice_flow.urls')),
]

