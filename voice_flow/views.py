import json
import logging
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    DynamicFormData,
    FormConfiguration,
    FormSubmission,
    MagicLinkSession,
)
from .serializers import (
    DynamicFormDataSerializer,
    FormConfigurationSerializer,
    FormSubmissionSerializer,
    MagicLinkSessionSerializer,
)

logger = logging.getLogger(__name__)


def home(request):
    """Home page"""
    return render(request, "voice_flow/home.html")


def voice_interface(request, session_id=None):
    """Voice interface for a specific session"""
    if not session_id:
        # Generate a temporary session ID for demo purposes
        session_id = str(uuid.uuid4())

    context = {
        "session_id": session_id,
        "websocket_url": f"ws://{request.get_host()}/ws/voice/{session_id}/",
    }
    return render(request, "voice_flow/voice_interface.html", context)


class FormConfigurationViewSet(viewsets.ModelViewSet):
    """ViewSet for form configuration CRUD operations"""

    queryset = FormConfiguration.objects.all()
    serializer_class = FormConfigurationSerializer

    @action(detail=True, methods=["get"])
    def magic_links(self, request, pk=None):
        """Get magic links for a form configuration"""
        form_config = self.get_object()
        sessions = MagicLinkSession.objects.filter(form_config=form_config)
        serializer = MagicLinkSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def generate_magic_link(self, request, pk=None):
        """Generate a new magic link for this form"""
        form_config = self.get_object()

        # Generate magic link
        from .configuration_utils import MagicLinkGenerator

        magic_link = MagicLinkGenerator.generate_magic_link(
            form_config_id=form_config.id,
            expires_in_hours=request.data.get("expires_in_hours", 24),
        )

        return Response(
            {"magic_link": magic_link, "form_name": form_config.name}
        )


class MagicLinkSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for magic link session read operations"""

    queryset = MagicLinkSession.objects.all()
    serializer_class = MagicLinkSessionSerializer

    @action(detail=True, methods=["get"])
    def form_data(self, request, pk=None):
        """Get form data for a magic link session"""
        session = self.get_object()
        form_data = DynamicFormData.objects.filter(session=session)
        serializer = DynamicFormDataSerializer(form_data, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def submit_form(self, request, pk=None):
        """Submit the form and trigger callback"""
        session = self.get_object()

        # Create form submission record
        submission = FormSubmission.objects.create(
            session=session,
            submitted_data=session.session_data,
            submission_status="completed",
        )

        # Trigger callback if configured
        if session.form_config.callback_url:
            from .configuration_utils import CallbackDelivery

            CallbackDelivery.deliver_callback(
                callback_url=session.form_config.callback_url,
                form_data=session.session_data,
                submission_id=submission.id,
            )

        return Response(
            {
                "submission_id": submission.id,
                "status": "completed",
                "message": "Form submitted successfully",
            }
        )


class DynamicFormDataViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for dynamic form data read operations"""

    queryset = DynamicFormData.objects.all()
    serializer_class = DynamicFormDataSerializer


class FormSubmissionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for form submission read operations"""

    queryset = FormSubmission.objects.all()
    serializer_class = FormSubmissionSerializer


@method_decorator(csrf_exempt, name="dispatch")
class SDKIntegrationView(View):
    """SDK endpoint for external integrations"""

    def get(self, request):
        """Get SDK information and examples"""
        return JsonResponse(
            {
                "sdk_version": "1.0.0",
                "endpoints": {
                    "create_form": "/api/sdk/create-form/",
                    "generate_magic_link": "/api/sdk/generate-magic-link/",
                    "get_form_data": "/api/sdk/form-data/",
                },
                "examples": {
                    "create_form": {
                        "method": "POST",
                        "url": "/api/sdk/create-form/",
                        "body": {
                            "name": "Customer Survey",
                            "description": "Collect customer feedback",
                            "callback_url": "https://your-app.com/webhook",
                            "ai_instructions": "Be friendly and conversational",
                        },
                    }
                },
            }
        )

    def post(self, request):
        """Create a new form configuration via SDK"""
        try:
            data = json.loads(request.body)

            # Create form configuration
            form_config = FormConfiguration.objects.create(
                name=data.get("name"),
                description=data.get("description"),
                callback_url=data.get("callback_url"),
                ai_instructions=data.get("ai_instructions"),
                form_schema=data.get("form_schema", {}),
            )

            # Generate magic link
            from .configuration_utils import MagicLinkGenerator

            magic_link = MagicLinkGenerator.generate_magic_link(
                form_config_id=form_config.id,
                expires_in_hours=data.get("expires_in_hours", 24),
            )

            return JsonResponse(
                {
                    "form_id": form_config.id,
                    "magic_link": magic_link,
                    "status": "created",
                }
            )

        except Exception as e:
            logger.error(f"SDK form creation error: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)
