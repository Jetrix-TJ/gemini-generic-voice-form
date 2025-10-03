"""
Callback system for receiving form data
Handles webhook delivery and retry logic
"""

import hashlib
import hmac
import json
import logging
from datetime import timedelta

import requests
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .configuration_utils import CallbackDelivery, FormValidator
from .models import FormConfiguration, FormSubmission, MagicLinkSession

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_callback(request, form_id):
    """
    Webhook endpoint for receiving form data
    This is where external systems can receive form submissions
    """
    try:
        # Get form configuration
        form_config = FormConfiguration.objects.get(id=form_id)

        # Parse request data
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)

        # Validate callback signature if configured
        if form_config.callback_secret:
            signature = request.headers.get("X-Signature")
            if not signature or not _verify_signature(
                request.body, form_config.callback_secret, signature
            ):
                return JsonResponse({"error": "Invalid signature"}, status=401)

        # Process the form submission
        result = _process_form_submission(form_config, data)

        return JsonResponse(result)

    except FormConfiguration.DoesNotExist:
        return JsonResponse(
            {"error": "Form configuration not found"}, status=404
        )
    except Exception as e:
        logger.error(f"Webhook callback error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


def _verify_signature(payload, secret, signature):
    """Verify HMAC signature for webhook security"""
    expected_signature = hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={expected_signature}"
    return hmac.compare_digest(signature, expected_signature)


def _process_form_submission(form_config, data):
    """Process form submission data"""
    try:
        # Validate form data against schema
        validation_result = FormValidator.validate_form_data(
            form_config.form_schema, data
        )

        if not validation_result["valid"]:
            return {
                "success": False,
                "error": "Validation failed",
                "validation_errors": validation_result["errors"],
            }

        # Create or update session
        session_id = data.get("session_id")
        if session_id:
            try:
                session = MagicLinkSession.objects.get(id=session_id)
            except MagicLinkSession.DoesNotExist:
                session = None
        else:
            session = None

        if not session:
            # Create new session
            session = MagicLinkSession.objects.create(
                form_config=form_config,
                magic_link_id=data.get("magic_link_id", "webhook"),
                expires_at=timezone.now() + timedelta(hours=24),
            )

        # Save form data
        for field_name, field_value in data.get("form_data", {}).items():
            from .models import DynamicFormData

            DynamicFormData.objects.update_or_create(
                session=session,
                field_name=field_name,
                defaults={
                    "field_value": str(field_value),
                    "field_type": "webhook",
                },
            )

        # Update session data
        session.session_data.update(data.get("form_data", {}))
        session.completion_status = "completed"
        session.completed_at = timezone.now()
        session.save()

        # Trigger callback delivery if configured
        if form_config.callback_url:
            callback_success = CallbackDelivery.deliver_form_data(
                session, data.get("form_data", {})
            )

            return {
                "success": True,
                "session_id": str(session.id),
                "callback_delivered": callback_success,
                "message": "Form submission processed successfully",
            }

        return {
            "success": True,
            "session_id": str(session.id),
            "message": "Form submission processed successfully",
        }

    except Exception as e:
        logger.error(f"Form submission processing error: {str(e)}")
        return {"success": False, "error": f"Processing failed: {str(e)}"}


@csrf_exempt
@require_http_methods(["POST"])
def retry_callback(request, submission_id):
    """
    Retry callback delivery for failed submissions
    """
    try:
        submission = FormSubmission.objects.get(id=submission_id)
        session = submission.session

        # Retry callback delivery
        success = CallbackDelivery.deliver_form_data(
            session, submission.submitted_data.get("form_data", {})
        )

        return JsonResponse(
            {
                "success": success,
                "message": (
                    "Callback retry completed"
                    if success
                    else "Callback retry failed"
                ),
            }
        )

    except FormSubmission.DoesNotExist:
        return JsonResponse({"error": "Submission not found"}, status=404)
    except Exception as e:
        logger.error(f"Callback retry error: {str(e)}")
        return JsonResponse({"error": "Retry failed"}, status=500)


class CallbackStatusView(View):
    """
    View for checking callback status and managing retries
    """

    def get(self, request, session_id):
        """Get callback status for a session"""
        try:
            session = MagicLinkSession.objects.get(id=session_id)
            submissions = FormSubmission.objects.filter(
                session=session
            ).order_by("-submission_timestamp")

            status_data = {
                "session_id": str(session.id),
                "form_name": session.form_config.name,
                "completion_status": session.completion_status,
                "callback_url": session.form_config.callback_url,
                "submissions": [],
            }

            for submission in submissions:
                status_data["submissions"].append(
                    {
                        "id": str(submission.id),
                        "timestamp": submission.submission_timestamp.isoformat(),
                        "callback_delivered": submission.callback_delivered,
                        "callback_attempts": submission.callback_attempts,
                        "callback_response_code": submission.callback_response_code,
                        "callback_error": (
                            submission.callback_response_body
                            if not submission.callback_delivered
                            else None
                        ),
                    }
                )

            return JsonResponse(status_data)

        except MagicLinkSession.DoesNotExist:
            return JsonResponse({"error": "Session not found"}, status=404)

    @method_decorator(csrf_exempt)
    def post(self, request, session_id):
        """Trigger callback retry for a session"""
        try:
            session = MagicLinkSession.objects.get(id=session_id)

            # Get latest submission
            latest_submission = (
                FormSubmission.objects.filter(session=session)
                .order_by("-submission_timestamp")
                .first()
            )

            if not latest_submission:
                return JsonResponse(
                    {"error": "No submissions found for this session"},
                    status=404,
                )

            # Retry callback
            success = CallbackDelivery.deliver_form_data(
                session, latest_submission.submitted_data.get("form_data", {})
            )

            return JsonResponse(
                {
                    "success": success,
                    "message": (
                        "Callback retry completed"
                        if success
                        else "Callback retry failed"
                    ),
                }
            )

        except MagicLinkSession.DoesNotExist:
            return JsonResponse({"error": "Session not found"}, status=404)


class WebhookTestView(View):
    """
    Test webhook endpoint for development
    """

    @method_decorator(csrf_exempt)
    def post(self, request):
        """Test webhook endpoint"""
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
                    "received_data": data,
                    "headers": dict(request.headers),
                    "timestamp": timezone.now().isoformat(),
                }
            )

        except Exception as e:
            return JsonResponse(
                {"success": False, "error": str(e)}, status=500
            )
