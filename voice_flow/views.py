"""
REST API Views for Voice Flow Service
"""
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import VoiceFormConfig, MagicLinkSession, APIKey
from .serializers import (
    VoiceFormConfigSerializer,
    MagicLinkSessionSerializer,
    GenerateSessionLinkSerializer,
    APIKeySerializer
)
from .tasks import send_webhook
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat()
    })


class VoiceFormConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Voice Form configurations
    """
    serializer_class = VoiceFormConfigSerializer
    lookup_field = 'form_id'
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return forms for the authenticated API key"""
        if hasattr(self.request, 'auth') and self.request.auth:
            # self.request.auth is the APIKey object
            return VoiceFormConfig.objects.filter(api_key=self.request.auth)
        return VoiceFormConfig.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create a new form configuration"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        form_config = serializer.save()
        
        # Get the response data with magic link
        response_serializer = self.get_serializer(form_config, context={'request': request})
        
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='generate-link')
    def generate_link(self, request, form_id=None):
        """
        Generate a magic link session for this form
        
        POST /api/forms/{form_id}/generate-link/
        {
            "session_data": {"user_id": "123", "source": "email"},
            "expires_in_hours": 24
        }
        """
        form_config = self.get_object()
        
        serializer = GenerateSessionLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create session
        expires_in_hours = serializer.validated_data['expires_in_hours']
        session_data = serializer.validated_data['session_data']
        
        session = MagicLinkSession.objects.create(
            form_config=form_config,
            session_data=session_data,
            expires_at=timezone.now() + timedelta(hours=expires_in_hours)
        )
        
        # Build response
        domain = f"{request.scheme}://{request.get_host()}"
        
        return Response({
            'session_id': session.session_id,
            'magic_link': session.get_magic_link(domain),
            'expires_at': session.expires_at.isoformat(),
            'expires_in_hours': expires_in_hours
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'], url_path='sessions')
    def list_sessions(self, request, form_id=None):
        """List all sessions for this form"""
        form_config = self.get_object()
        sessions = form_config.sessions.all().order_by('-created_at')
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            sessions = sessions.filter(status=status_filter)
        
        # Pagination
        page = self.paginate_queryset(sessions)
        if page is not None:
            serializer = MagicLinkSessionSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = MagicLinkSessionSerializer(sessions, many=True, context={'request': request})
        return Response(serializer.data)


class MagicLinkSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing Magic Link sessions
    """
    serializer_class = MagicLinkSessionSerializer
    lookup_field = 'session_id'
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return sessions for forms owned by the authenticated API key"""
        if hasattr(self.request, 'auth') and self.request.auth:
            # self.request.auth is the APIKey object
            return MagicLinkSession.objects.filter(form_config__api_key=self.request.auth)
        return MagicLinkSession.objects.none()
    
    @action(detail=True, methods=['post'], url_path='retry-webhook')
    def retry_webhook(self, request, session_id=None):
        """Retry sending webhook for a completed session"""
        session = self.get_object()
        
        if session.status != 'completed':
            return Response(
                {'error': 'Session must be completed to retry webhook'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Trigger webhook task
        send_webhook.delay(session_id)
        
        return Response({
            'message': 'Webhook retry scheduled',
            'session_id': session_id
        })


# Public views (no authentication required)

@api_view(['GET'])
@permission_classes([AllowAny])
def form_interface(request, form_id):
    """
    Render the voice interface for a form
    This is accessed via the base magic link
    """
    form_config = get_object_or_404(VoiceFormConfig, form_id=form_id, is_active=True)
    
    # Create a new session
    default_expiry = settings.VOICE_FORM_SETTINGS.get('DEFAULT_SESSION_EXPIRY_HOURS', 24)
    session = MagicLinkSession.objects.create(
        form_config=form_config,
        expires_at=timezone.now() + timedelta(hours=default_expiry)
    )
    
    context = {
        'form_config': form_config,
        'session': session,
        'ws_scheme': 'wss' if request.is_secure() else 'ws',
        'host': request.get_host()
    }
    
    # Use Live API interface if enabled
    use_live_api = settings.VOICE_FORM_SETTINGS.get('USE_LIVE_API', True)
    template = 'voice_flow/live_voice_interface.html' if use_live_api else 'voice_flow/voice_interface.html'
    
    return render(request, template, context)


@api_view(['GET'])
@permission_classes([AllowAny])
def session_interface(request, session_id):
    """
    Render the voice interface for a specific session
    This is accessed via the session-specific magic link
    """
    session = get_object_or_404(MagicLinkSession, session_id=session_id)
    
    # Check if expired
    if session.is_expired():
        return render(request, 'voice_flow/session_expired.html', {'session': session})
    
    # Check if already completed
    if session.status == 'completed':
        return render(request, 'voice_flow/session_completed.html', {'session': session})
    
    # Mark as started if pending
    if session.status == 'pending':
        session.mark_started()
    
    context = {
        'form_config': session.form_config,
        'session': session,
        'ws_scheme': 'wss' if request.is_secure() else 'ws',
        'host': request.get_host()
    }
    
    # Use Live API interface if enabled
    use_live_api = settings.VOICE_FORM_SETTINGS.get('USE_LIVE_API', True)
    template = 'voice_flow/live_voice_interface.html' if use_live_api else 'voice_flow/voice_interface.html'
    
    return render(request, template, context)


@api_view(['GET'])
@permission_classes([AllowAny])
def home(request):
    """Home page with documentation"""
    return render(request, 'voice_flow/home.html')


@api_view(['GET'])
@permission_classes([AllowAny])
def create_form_page(request):
    """Render the Create Form UI page"""
    return render(request, 'voice_flow/create_form.html')


@api_view(['POST'])
@permission_classes([AllowAny])
def dev_create_api_key(request):
    """Create a development API key when DEBUG=True.
    Returns 403 if DEBUG is False.
    """
    if not settings.DEBUG:
        return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
    name = request.data.get('name') or 'Dev Key'
    api_key = APIKey.objects.create(name=name)
    return Response({'key': api_key.key, 'name': api_key.name}, status=status.HTTP_201_CREATED)


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing API Keys (admin only)
    """
    serializer_class = APIKeySerializer
    queryset = APIKey.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return API keys for the authenticated user"""
        if hasattr(self.request, 'auth') and self.request.auth:
            # self.request.auth is the APIKey object
            return APIKey.objects.filter(id=self.request.auth.id)
        return APIKey.objects.none()

