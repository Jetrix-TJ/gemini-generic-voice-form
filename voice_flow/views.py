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
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.safestring import mark_safe
import json
from django.http import HttpResponse
import csv
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from django.shortcuts import redirect
from .models import VoiceFormConfig, MagicLinkSession, APIKey
from .serializers import (
    VoiceFormConfigSerializer,
    MagicLinkSessionSerializer,
    GenerateSessionLinkSerializer,
    APIKeySerializer
)
from .tasks import send_webhook
from .ai_service import ai_service
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
        """Return forms for the authenticated principal (session user or API key)."""
        # API key auth path
        if hasattr(self.request, 'auth') and self.request.auth:
            return VoiceFormConfig.objects.filter(api_key=self.request.auth)
        # Session user path
        user = getattr(self.request, 'user', None)
        if getattr(user, 'is_authenticated', False):
            return VoiceFormConfig.objects.filter(api_key__user=user)
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
        """Return sessions for forms owned by the authenticated principal (session user or API key)."""
        # API key auth path
        if hasattr(self.request, 'auth') and self.request.auth:
            return MagicLinkSession.objects.filter(form_config__api_key=self.request.auth)
        # Session user path
        user = getattr(self.request, 'user', None)
        if getattr(user, 'is_authenticated', False):
            return MagicLinkSession.objects.filter(form_config__api_key__user=user)
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
        # Ensure webhook URL is configured
        if not getattr(session.form_config, 'callback_url', None):
            return Response(
                {'error': 'No callback_url configured for this form'},
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
@ensure_csrf_cookie
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
    
    # Always use Live API interface (single unified template)
    return render(request, 'voice_flow/live_voice_interface.html', context)


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
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
    
    # Always use Live API interface (single unified template)
    return render(request, 'voice_flow/live_voice_interface.html', context)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def finalize_session_public(request, session_id):
    """Public endpoint to finalize a session with explicit field values.
    Body: { "fields": {"field_name": value, ...} }
    """
    try:
        session = MagicLinkSession.objects.select_related('form_config').get(session_id=session_id)
    except MagicLinkSession.DoesNotExist:
        return Response({'detail': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if session.is_expired():
        return Response({'detail': 'Session expired'}, status=status.HTTP_400_BAD_REQUEST)
    
    data = request.data or {}
    fields = data.get('fields') or {}
    if not isinstance(fields, dict):
        return Response({'detail': 'Invalid fields payload'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Update collected data
    for k, v in fields.items():
        session.collected_data[k] = v
    session.fields_completed = len([v for v in session.collected_data.values() if v is not None])
    session.save(update_fields=['collected_data', 'fields_completed'])
    
    return Response({'ok': True, 'collected_data': session.collected_data})


@api_view(['GET'])
@permission_classes([AllowAny])
def home(request):
    """Home page with documentation"""
    return render(request, 'voice_flow/home.html')


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def create_form_page(request):
    """Render the Create Form UI page"""
    return render(request, 'voice_flow/create_form.html')


# Web UI: Authenticated dashboard
@login_required
def dashboard(request):
    """Simple dashboard listing forms for the logged-in user's API keys."""
    # Forms are owned via APIKey.user → VoiceFormConfig.api_key
    user = request.user
    api_keys = APIKey.objects.filter(user=user)
    forms = VoiceFormConfig.objects.filter(api_key__in=api_keys).order_by('-created_at')
    total_forms = forms.count()
    total_sessions = 0
    try:
        total_sessions = sum(f.sessions.count() for f in forms)
    except Exception:
        pass
    context = {
        'api_keys': api_keys,
        'forms': forms,
        'total_forms': total_forms,
        'total_sessions': total_sessions,
    }
    return render(request, 'voice_flow/dashboard.html', context)


@login_required
@require_POST
def link_api_key(request):
    """Link an existing API key to the logged-in user (standard Django view)."""
    try:
        key = request.POST.get('key')
        if not key:
            return JsonResponse({'error': 'key is required'}, status=400)
        try:
            api_key = APIKey.objects.get(key=key)
        except APIKey.DoesNotExist:
            return JsonResponse({'error': 'API key not found'}, status=404)
        api_key.user = request.user
        api_key.save(update_fields=['user'])
        return JsonResponse({'ok': True, 'key': api_key.key, 'name': api_key.name})
    except Exception as e:
        logger.error(f"link_api_key error: {e}")
        return JsonResponse({'error': 'Failed to link key'}, status=500)


@login_required
@require_POST
def create_linked_api_key(request):
    """Create a new API key owned by the logged-in user (standard Django view)."""
    name = request.POST.get('name') or 'My API Key'
    api_key = APIKey.objects.create(name=name, user=request.user)
    return JsonResponse({'key': api_key.key, 'name': api_key.name}, status=201)


@login_required
def form_detail(request, form_id):
    """Detail page for a form: show summaries and JSON for sessions."""
    try:
        form = VoiceFormConfig.objects.get(form_id=form_id, api_key__user=request.user)
    except VoiceFormConfig.DoesNotExist:
        return render(request, 'voice_flow/home.html', {
            'error': 'Form not found or not owned by you.'
        })
    # Recent sessions
    sessions = list(form.sessions.all().order_by('-created_at')[:100])

    def build_summary_text(session):
        # Prefer stored LLM summary when available
        if getattr(session, 'summary_text', None):
            return session.summary_text
        data = session.collected_data or {}
        if isinstance(data, dict) and data:
            try:
                pairs = [f"{k}: {data.get(k)}" for k in data.keys() if data.get(k) not in (None, '')]
                return '; '.join(pairs) if pairs else '—'
            except Exception:
                pass
        # Fallback: show number of messages if we have a conversation
        try:
            msgs = session.conversation_history or []
            if msgs:
                return f"{len(msgs)} messages captured."
        except Exception:
            pass
        return '—'

    session_rows = []
    for s in sessions:
        session_rows.append({
            'session_id': s.session_id,
            'status': s.status,
            'created_at': s.created_at,
            'completed_at': s.completed_at,
            'summary': build_summary_text(s),
            'json': json.dumps(s.collected_data or {}, indent=2),
        })

    form_json = json.dumps({
        'form_id': form.form_id,
        'name': form.name,
        'description': form.description,
        'fields': form.fields,
        'ai_prompt': form.ai_prompt,
        'settings': form.settings,
    }, indent=2)

    context = {
        'form': form,
        'session_rows': session_rows,
        'form_json': form_json,
    }
    return render(request, 'voice_flow/form_detail.html', context)


@login_required
def export_form_csv(request, form_id):
    """Export all session responses for a form as CSV (one row per session)."""
    try:
        form = VoiceFormConfig.objects.get(form_id=form_id, api_key__user=request.user)
    except VoiceFormConfig.DoesNotExist:
        return HttpResponse('Form not found or not owned by you.', status=404)

    sessions_qs = form.sessions.all().order_by('created_at')
    sessions = list(sessions_qs)

    # Build dynamic columns from union of collected_data keys
    field_names = set()
    for s in sessions:
        try:
            data = s.collected_data or {}
            if isinstance(data, dict):
                field_names.update(list(data.keys()))
        except Exception:
            pass
    sorted_fields = sorted(field_names)

    # CSV headers
    headers = [
        'session_id', 'status', 'created_at', 'completed_at', 'summary_text'
    ] + sorted_fields

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{form.form_id}_responses.csv"'

    writer = csv.writer(response)
    writer.writerow(headers)

    for s in sessions:
        row = [
            s.session_id,
            s.status,
            s.created_at.isoformat() if s.created_at else '',
            s.completed_at.isoformat() if s.completed_at else '',
            getattr(s, 'summary_text', '') or ''
        ]
        data = s.collected_data or {}
        for fname in sorted_fields:
            val = data.get(fname)
            if isinstance(val, (dict, list)):
                try:
                    val = json.dumps(val, ensure_ascii=False)
                except Exception:
                    val = str(val)
            row.append('' if val is None else val)
        writer.writerow(row)

    return response


def signup(request):
    """Public signup to create an account and auto-provision an API key."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                APIKey.objects.create(name='Default Key', user=user)
            except Exception:
                pass
            auth_login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form})


@api_view(['POST'])
@permission_classes([AllowAny])
def generate_form_schema(request):
    """Generate a form schema from a natural language description.

    Body: { "formDesc": "...", "history": [ {role, content}, ... ] }
    Returns: { "schema": {...}, "clarifying_questions": [...] }
    """
    data = request.data or {}
    form_desc = data.get('formDesc') or data.get('formdesc') or data.get('description') or ''
    history = data.get('history') or []
    result = ai_service.generate_form_schema(form_desc, history)
    return Response(result)


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

