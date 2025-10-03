"""
Magic link views for accessing forms
Handles magic link validation and form access
"""

import json
import logging

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .configuration_utils import FormValidator, MagicLinkGenerator
from .models import DynamicFormData, FormConfiguration, MagicLinkSession

logger = logging.getLogger(__name__)


def magic_link_access(request, magic_link_id):
    """
    Handle magic link access and display form interface
    """
    # Validate magic link
    session = MagicLinkGenerator.validate_magic_link(magic_link_id)

    if not session:
        # Magic link is invalid or expired
        return render(
            request,
            "voice_flow/magic_link_error.html",
            {
                "error_type": "invalid_or_expired",
                "error_message": "This magic link is invalid or has expired.",
            },
        )

    # Check if session is already completed
    if session.completion_status == "completed":
        return render(
            request,
            "voice_flow/magic_link_completed.html",
            {"session": session, "form_config": session.form_config},
        )

    # Get current form data
    form_data = DynamicFormData.objects.filter(session=session)
    current_data = {field.field_name: field.field_value for field in form_data}

    # Build WebSocket URL
    websocket_url = f"ws://{request.get_host()}/ws/voice/{magic_link_id}/"

    context = {
        "session": session,
        "form_config": session.form_config,
        "form_schema": session.form_config.form_schema,
        "current_data": current_data,
        "websocket_url": websocket_url,
        "magic_link_id": magic_link_id,
    }

    return render(request, "voice_flow/magic_link_interface.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def magic_link_submit(request, magic_link_id):
    """
    Handle form submission via magic link
    """
    try:
        # Validate magic link
        session = MagicLinkGenerator.validate_magic_link(magic_link_id)

        if not session:
            return JsonResponse(
                {"success": False, "error": "Invalid or expired magic link"},
                status=400,
            )

        # Parse form data
        try:
            form_data = json.loads(request.body)
        except json.JSONDecodeError:
            form_data = request.POST.dict()

        # Validate form data against schema
        validation_result = FormValidator.validate_form_data(
            session.form_config.form_schema, form_data
        )

        if not validation_result["valid"]:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Validation failed",
                    "validation_errors": validation_result["errors"],
                },
                status=400,
            )

        # Save form data
        for field_name, field_value in form_data.items():
            DynamicFormData.objects.update_or_create(
                session=session,
                field_name=field_name,
                defaults={
                    "field_value": str(field_value),
                    "field_type": "form_submission",
                },
            )

        # Update session
        session.session_data.update(form_data)
        session.completion_status = "completed"
        session.completed_at = timezone.now()
        session.save()

        # Trigger callback if configured
        from .configuration_utils import CallbackDelivery

        if session.form_config.callback_url:
            callback_success = CallbackDelivery.deliver_form_data(
                session, form_data
            )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Form submitted successfully",
                    "callback_delivered": callback_success,
                    "session_id": str(session.id),
                }
            )

        return JsonResponse(
            {
                "success": True,
                "message": "Form submitted successfully",
                "session_id": str(session.id),
            }
        )

    except Exception as e:
        logger.error(f"Magic link submission error: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Submission failed: {str(e)}"},
            status=500,
        )


class MagicLinkWebSocketConsumer(View):
    """
    WebSocket consumer for magic link voice interactions
    """

    def get(self, request, magic_link_id):
        """Get WebSocket connection info"""
        session = MagicLinkGenerator.validate_magic_link(magic_link_id)

        if not session:
            return JsonResponse(
                {"error": "Invalid or expired magic link"}, status=400
            )

        return JsonResponse(
            {
                "magic_link_id": magic_link_id,
                "session_id": str(session.id),
                "form_name": session.form_config.name,
                "websocket_url": f"ws://{request.get_host()}/ws/voice/{magic_link_id}/",
            }
        )


def magic_link_status(request, magic_link_id):
    """
    Get magic link status and form data
    """
    session = MagicLinkGenerator.validate_magic_link(magic_link_id)

    if not session:
        return JsonResponse(
            {"valid": False, "error": "Invalid or expired magic link"}
        )

    # Get form data
    form_data = DynamicFormData.objects.filter(session=session)
    current_data = {field.field_name: field.field_value for field in form_data}

    return JsonResponse(
        {
            "valid": True,
            "session_id": str(session.id),
            "form_name": session.form_config.name,
            "completion_status": session.completion_status,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "form_data": current_data,
            "progress": _calculate_progress(session),
        }
    )


def _calculate_progress(session):
    """Calculate form completion progress"""
    form_schema = session.form_config.form_schema
    total_fields = 0
    completed_fields = 0

    for section in form_schema.get("sections", []):
        for field in section.get("fields", []):
            if field.get("required", False):
                total_fields += 1
                if DynamicFormData.objects.filter(
                    session=session, field_name=field["name"]
                ).exists():
                    completed_fields += 1

    if total_fields == 0:
        return 100

    return round((completed_fields / total_fields) * 100, 1)


def magic_link_embed(request, magic_link_id):
    """
    Embeddable version of magic link form
    """
    session = MagicLinkGenerator.validate_magic_link(magic_link_id)

    if not session:
        return JsonResponse(
            {"error": "Invalid or expired magic link"}, status=400
        )

    # Get current form data
    form_data = DynamicFormData.objects.filter(session=session)
    current_data = {field.field_name: field.field_value for field in form_data}

    # Build WebSocket URL
    websocket_url = f"ws://{request.get_host()}/ws/voice/{magic_link_id}/"

    context = {
        "session": session,
        "form_config": session.form_config,
        "form_schema": session.form_config.form_schema,
        "current_data": current_data,
        "websocket_url": websocket_url,
        "magic_link_id": magic_link_id,
        "embedded": True,
    }

    return render(request, "voice_flow/magic_link_embed.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def magic_link_webhook_test(request, magic_link_id):
    """
    Test webhook for magic link form
    """
    session = MagicLinkGenerator.validate_magic_link(magic_link_id)

    if not session:
        return JsonResponse(
            {"error": "Invalid or expired magic link"}, status=400
        )

    # Test webhook delivery
    from .configuration_utils import CallbackDelivery

    test_data = {
        "test_field": "test_value",
        "timestamp": timezone.now().isoformat(),
    }

    success = CallbackDelivery.deliver_form_data(session, test_data)

    return JsonResponse(
        {
            "success": success,
            "message": (
                "Webhook test completed" if success else "Webhook test failed"
            ),
            "callback_url": session.form_config.callback_url,
        }
    )


def magic_link_qr_code(request, magic_link_id):
    """
    Generate QR code for magic link
    """
    session = MagicLinkGenerator.validate_magic_link(magic_link_id)

    if not session:
        raise Http404("Magic link not found")

    # Generate QR code URL
    base_url = request.build_absolute_uri("/")
    magic_link_url = f"{base_url}voice/magic/{magic_link_id}/"

    context = {
        "session": session,
        "form_config": session.form_config,
        "magic_link_url": magic_link_url,
        "qr_code_data": magic_link_url,
    }

    return render(request, "voice_flow/magic_link_qr.html", context)
