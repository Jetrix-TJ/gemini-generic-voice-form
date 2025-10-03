"""
SDK/Plugin interface for easy integration
Provides simple API endpoints for external systems
"""

import json
import logging
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .configuration_utils import (
    CallbackDelivery,
    FormConfigBuilder,
    FormValidator,
    MagicLinkGenerator,
    PreBuiltForms,
)
from .models import DynamicFormData, FormConfiguration, MagicLinkSession

logger = logging.getLogger(__name__)


class SDKFormManagementView(View):
    """
    SDK endpoint for form management
    """

    @method_decorator(csrf_exempt)
    def post(self, request):
        """Create a new form configuration"""
        try:
            data = json.loads(request.body)

            # Extract form configuration
            form_name = data.get("name")
            form_description = data.get("description", "")
            callback_url = data.get("callback_url")
            callback_headers = data.get("callback_headers", {})
            callback_secret = data.get("callback_secret")
            ai_instructions = data.get("ai_instructions", "")
            magic_link_expiry = data.get("magic_link_expiry_hours", 24)

            # Build form schema
            if data.get("use_prebuilt"):
                prebuilt_type = data.get("prebuilt_type", "patient_intake")
                if prebuilt_type == "patient_intake":
                    form_schema = PreBuiltForms.patient_intake_form()
                elif prebuilt_type == "contact_form":
                    form_schema = PreBuiltForms.contact_form()
                elif prebuilt_type == "job_application":
                    form_schema = PreBuiltForms.job_application_form()
                else:
                    form_schema = PreBuiltForms.patient_intake_form()

                # Override with custom settings
                form_schema["name"] = form_name
                form_schema["description"] = form_description
                if callback_url:
                    form_schema["callback_settings"]["url"] = callback_url
                if callback_headers:
                    form_schema["callback_settings"][
                        "headers"
                    ] = callback_headers
                if callback_secret:
                    form_schema["callback_settings"][
                        "secret"
                    ] = callback_secret
                if ai_instructions:
                    form_schema["ai_instructions"] = ai_instructions
            else:
                # Build custom form from sections
                builder = FormConfigBuilder(form_name, form_description)

                if ai_instructions:
                    builder.set_ai_instructions(ai_instructions)

                if callback_url:
                    builder.set_callback_url(
                        callback_url, callback_headers, callback_secret
                    )

                # Add sections and fields
                for section_data in data.get("sections", []):
                    section = builder.add_section(
                        section_data["title"],
                        section_data.get("description", ""),
                    )

                    for field_data in section_data.get("fields", []):
                        builder.add_field(None, field_data)

                form_schema = builder.build()

            # Create form configuration
            form_config = FormConfiguration.objects.create(
                name=form_name,
                description=form_description,
                form_schema=form_schema,
                callback_url=callback_url,
                callback_headers=callback_headers,
                callback_secret=callback_secret,
                ai_instructions=ai_instructions,
                magic_link_expiry_hours=magic_link_expiry,
            )

            return JsonResponse(
                {
                    "success": True,
                    "form_id": str(form_config.id),
                    "form_name": form_config.name,
                    "magic_link_url": form_config.magic_link_url,
                    "webhook_url": f"/api/webhook/{form_config.id}/",
                    "message": "Form created successfully",
                }
            )

        except Exception as e:
            logger.error(f"Form creation error: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Form creation failed: {str(e)}"},
                status=500,
            )

    def get(self, request):
        """List all form configurations"""
        try:
            forms = FormConfiguration.objects.filter(is_active=True)

            forms_data = []
            for form in forms:
                forms_data.append(
                    {
                        "id": str(form.id),
                        "name": form.name,
                        "description": form.description,
                        "created_at": form.created_at.isoformat(),
                        "magic_link_url": form.magic_link_url,
                        "webhook_url": f"/api/webhook/{form.id}/",
                        "callback_configured": bool(form.callback_url),
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "forms": forms_data,
                    "count": len(forms_data),
                }
            )

        except Exception as e:
            logger.error(f"Form listing error: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Form listing failed: {str(e)}"},
                status=500,
            )


class SDKMagicLinkView(View):
    """
    SDK endpoint for magic link generation
    """

    @method_decorator(csrf_exempt)
    def post(self, request):
        """Generate magic link for form access"""
        try:
            data = json.loads(request.body)

            form_id = data.get("form_id")
            expiry_hours = data.get("expiry_hours", 24)
            custom_data = data.get("custom_data", {})

            if not form_id:
                return JsonResponse(
                    {"success": False, "error": "form_id is required"},
                    status=400,
                )

            # Generate magic link
            magic_link = MagicLinkGenerator.create_magic_link(
                form_id, expiry_hours, custom_data
            )

            return JsonResponse(
                {
                    "success": True,
                    "magic_link": magic_link,
                    "expires_in_hours": expiry_hours,
                    "message": "Magic link generated successfully",
                }
            )

        except FormConfiguration.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Form configuration not found"},
                status=404,
            )
        except Exception as e:
            logger.error(f"Magic link generation error: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Magic link generation failed: {str(e)}",
                },
                status=500,
            )


class SDKFormDataView(View):
    """
    SDK endpoint for retrieving form data
    """

    def get(self, request, session_id):
        """Get form data for a session"""
        try:
            session = MagicLinkSession.objects.get(id=session_id)

            # Get all form data
            form_data = DynamicFormData.objects.filter(session=session)

            # Build response data
            data_dict = {}
            for field in form_data:
                data_dict[field.field_name] = field.field_value

            # Get form submissions
            from .models import FormSubmission

            submissions = FormSubmission.objects.filter(
                session=session
            ).order_by("-submission_timestamp")

            submission_data = []
            for submission in submissions:
                submission_data.append(
                    {
                        "id": str(submission.id),
                        "timestamp": submission.submission_timestamp.isoformat(),
                        "callback_delivered": submission.callback_delivered,
                        "callback_attempts": submission.callback_attempts,
                    }
                )

            return JsonResponse(
                {
                    "success": True,
                    "session_id": str(session.id),
                    "magic_link_id": session.magic_link_id,
                    "form_name": session.form_config.name,
                    "completion_status": session.completion_status,
                    "created_at": session.created_at.isoformat(),
                    "completed_at": (
                        session.completed_at.isoformat()
                        if session.completed_at
                        else None
                    ),
                    "form_data": data_dict,
                    "submissions": submission_data,
                }
            )

        except MagicLinkSession.DoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Session not found"}, status=404
            )
        except Exception as e:
            logger.error(f"Form data retrieval error: {str(e)}")
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Form data retrieval failed: {str(e)}",
                },
                status=500,
            )


class SDKStatusView(View):
    """
    SDK status and health check endpoint
    """

    def get(self, request):
        """Get SDK status and available endpoints"""
        return JsonResponse(
            {
                "success": True,
                "service": "Voice Flow SDK",
                "version": "1.0.0",
                "status": "healthy",
                "endpoints": {
                    "create_form": "POST /api/sdk/forms/",
                    "list_forms": "GET /api/sdk/forms/",
                    "generate_magic_link": "POST /api/sdk/magic-link/",
                    "get_form_data": "GET /api/sdk/form-data/{session_id}/",
                    "webhook_callback": "POST /api/webhook/{form_id}/",
                    "test_webhook": "POST /api/sdk/test-webhook/",
                },
                "prebuilt_forms": [
                    "patient_intake",
                    "contact_form",
                    "job_application",
                ],
                "features": [
                    "Dynamic form configuration",
                    "Magic link generation",
                    "Webhook callbacks",
                    "Real-time voice processing",
                    "AI-powered form completion",
                    "File upload support",
                ],
            }
        )


@csrf_exempt
@require_http_methods(["POST"])
def test_webhook(request):
    """
    Test webhook endpoint for development
    """
    try:
        data = (
            json.loads(request.body)
            if request.content_type == "application/json"
            else request.POST.dict()
        )

        # Echo back the received data
        return JsonResponse(
            {
                "success": True,
                "message": "Webhook test successful",
                "received_data": data,
                "headers": dict(request.headers),
                "timestamp": timezone.now().isoformat(),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


class SDKQuickStartView(View):
    """
    Quick start endpoint with example configurations
    """

    def get(self, request):
        """Get quick start examples"""
        examples = {
            "simple_contact_form": {
                "name": "Contact Form",
                "description": "Simple contact form example",
                "use_prebuilt": True,
                "prebuilt_type": "contact_form",
                "callback_url": "https://your-domain.com/webhook/contact",
                "callback_secret": "your-webhook-secret",
            },
            "patient_intake": {
                "name": "Patient Intake Form",
                "description": "Medical patient intake form",
                "use_prebuilt": True,
                "prebuilt_type": "patient_intake",
                "callback_url": "https://your-domain.com/webhook/patient",
                "callback_secret": "your-webhook-secret",
                "ai_instructions": "You are a medical assistant collecting patient information. Be professional and empathetic.",
            },
            "custom_form": {
                "name": "Custom Form",
                "description": "Custom form with multiple sections",
                "sections": [
                    {
                        "title": "Personal Information",
                        "description": "Basic personal details",
                        "fields": [
                            {
                                "name": "full_name",
                                "label": "Full Name",
                                "type": "text",
                                "required": True,
                            },
                            {
                                "name": "email",
                                "label": "Email Address",
                                "type": "email",
                                "required": True,
                            },
                        ],
                    }
                ],
                "callback_url": "https://your-domain.com/webhook/custom",
                "callback_secret": "your-webhook-secret",
            },
        }

        return JsonResponse(
            {
                "success": True,
                "examples": examples,
                "usage": {
                    "create_form": "POST /api/sdk/forms/ with example JSON",
                    "generate_magic_link": 'POST /api/sdk/magic-link/ with {"form_id": "your-form-id"}',
                    "receive_data": "Set up webhook endpoint to receive POST requests with form data",
                },
            }
        )
