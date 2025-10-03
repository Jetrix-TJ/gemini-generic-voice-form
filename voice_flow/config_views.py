"""
Web-based configuration interface for form management
Allows users to create and configure forms without coding
"""

import json
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .configuration_utils import (
    FormConfigBuilder,
    MagicLinkGenerator,
    PreBuiltForms,
)
from .models import DynamicFormData, FormConfiguration, MagicLinkSession

logger = logging.getLogger(__name__)


def config_dashboard(request):
    """Main configuration dashboard"""
    forms = FormConfiguration.objects.filter(is_active=True).order_by(
        "-created_at"
    )

    context = {
        "forms": forms,
        "total_forms": forms.count(),
        "active_sessions": MagicLinkSession.objects.filter(
            completion_status="active"
        ).count(),
        "completed_sessions": MagicLinkSession.objects.filter(
            completion_status="completed"
        ).count(),
    }

    return render(request, "voice_flow/config_dashboard.html", context)


def create_form(request):
    """Create new form configuration"""
    if request.method == "POST":
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
                    "redirect_url": f"/config/forms/{form_config.id}/",
                }
            )

        except Exception as e:
            logger.error(f"Form creation error: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Form creation failed: {str(e)}"},
                status=500,
            )

    # GET request - show form creation page
    context = {
        "prebuilt_forms": [
            {
                "id": "patient_intake",
                "name": "Patient Intake Form",
                "description": "Comprehensive medical intake form",
            },
            {
                "id": "contact_form",
                "name": "Contact Form",
                "description": "Simple contact information form",
            },
            {
                "id": "job_application",
                "name": "Job Application Form",
                "description": "Employment application form",
            },
        ]
    }

    return render(request, "voice_flow/create_form.html", context)


def form_detail(request, form_id):
    """View and manage specific form configuration"""
    form_config = get_object_or_404(FormConfiguration, id=form_id)

    # Get form sessions
    sessions = MagicLinkSession.objects.filter(
        form_config=form_config
    ).order_by("-created_at")[
        :20
    ]  # Last 20 sessions

    context = {
        "form_config": form_config,
        "sessions": sessions,
        "total_sessions": MagicLinkSession.objects.filter(
            form_config=form_config
        ).count(),
        "active_sessions": MagicLinkSession.objects.filter(
            form_config=form_config, completion_status="active"
        ).count(),
        "completed_sessions": MagicLinkSession.objects.filter(
            form_config=form_config, completion_status="completed"
        ).count(),
    }

    return render(request, "voice_flow/form_detail.html", context)


def generate_magic_link(request, form_id):
    """Generate magic link for a form"""
    form_config = get_object_or_404(FormConfiguration, id=form_id)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            expiry_hours = data.get(
                "expiry_hours", form_config.magic_link_expiry_hours
            )
            custom_data = data.get("custom_data", {})

            # Generate magic link
            magic_link = MagicLinkGenerator.create_magic_link(
                form_id, expiry_hours, custom_data
            )

            return JsonResponse(
                {
                    "success": True,
                    "magic_link": magic_link,
                    "expires_in_hours": expiry_hours,
                }
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

    # GET request - show magic link generation form
    return render(
        request,
        "voice_flow/generate_magic_link.html",
        {"form_config": form_config},
    )


def session_detail(request, session_id):
    """View detailed session information"""
    session = get_object_or_404(MagicLinkSession, id=session_id)

    # Get form data
    form_data = DynamicFormData.objects.filter(session=session).order_by(
        "collected_at"
    )

    # Get submissions
    from .models import FormSubmission

    submissions = FormSubmission.objects.filter(session=session).order_by(
        "-submission_timestamp"
    )

    context = {
        "session": session,
        "form_data": form_data,
        "submissions": submissions,
        "form_config": session.form_config,
    }

    return render(request, "voice_flow/session_detail.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def update_form_config(request, form_id):
    """Update form configuration"""
    form_config = get_object_or_404(FormConfiguration, id=form_id)

    try:
        data = json.loads(request.body)

        # Update basic fields
        if "name" in data:
            form_config.name = data["name"]
        if "description" in data:
            form_config.description = data["description"]
        if "callback_url" in data:
            form_config.callback_url = data["callback_url"]
        if "callback_headers" in data:
            form_config.callback_headers = data["callback_headers"]
        if "callback_secret" in data:
            form_config.callback_secret = data["callback_secret"]
        if "ai_instructions" in data:
            form_config.ai_instructions = data["ai_instructions"]
        if "magic_link_expiry_hours" in data:
            form_config.magic_link_expiry_hours = data[
                "magic_link_expiry_hours"
            ]

        # Update form schema if provided
        if "form_schema" in data:
            form_config.form_schema = data["form_schema"]

        form_config.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Form configuration updated successfully",
            }
        )

    except Exception as e:
        logger.error(f"Form update error: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Form update failed: {str(e)}"},
            status=500,
        )


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_form_config(request, form_id):
    """Delete form configuration"""
    form_config = get_object_or_404(FormConfiguration, id=form_id)

    try:
        # Deactivate instead of delete to preserve data
        form_config.is_active = False
        form_config.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Form configuration deactivated successfully",
            }
        )

    except Exception as e:
        logger.error(f"Form deletion error: {str(e)}")
        return JsonResponse(
            {"success": False, "error": f"Form deletion failed: {str(e)}"},
            status=500,
        )


class FormBuilderView(View):
    """
    Visual form builder interface
    """

    def get(self, request):
        """Show form builder interface"""
        return render(request, "voice_flow/form_builder.html")

    @method_decorator(csrf_exempt)
    def post(self, request):
        """Save form configuration from builder"""
        try:
            data = json.loads(request.body)

            # Extract form configuration
            form_name = data.get("name")
            form_description = data.get("description", "")
            sections = data.get("sections", [])
            callback_url = data.get("callback_url")
            callback_headers = data.get("callback_headers", {})
            callback_secret = data.get("callback_secret")
            ai_instructions = data.get("ai_instructions", "")
            magic_link_expiry = data.get("magic_link_expiry_hours", 24)

            # Build form schema
            builder = FormConfigBuilder(form_name, form_description)

            if ai_instructions:
                builder.set_ai_instructions(ai_instructions)

            if callback_url:
                builder.set_callback_url(
                    callback_url, callback_headers, callback_secret
                )

            # Add sections and fields
            for section_data in sections:
                section = builder.add_section(
                    section_data["title"], section_data.get("description", "")
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
                    "redirect_url": f"/config/forms/{form_config.id}/",
                }
            )

        except Exception as e:
            logger.error(f"Form builder save error: {str(e)}")
            return JsonResponse(
                {"success": False, "error": f"Form save failed: {str(e)}"},
                status=500,
            )


def analytics_dashboard(request):
    """Analytics dashboard for form usage"""
    # Get overall statistics
    total_forms = FormConfiguration.objects.filter(is_active=True).count()
    total_sessions = MagicLinkSession.objects.count()
    active_sessions = MagicLinkSession.objects.filter(
        completion_status="active"
    ).count()
    completed_sessions = MagicLinkSession.objects.filter(
        completion_status="completed"
    ).count()

    # Get recent activity
    recent_sessions = MagicLinkSession.objects.order_by("-created_at")[:10]

    # Get form usage statistics
    form_stats = []
    for form_config in FormConfiguration.objects.filter(is_active=True):
        sessions_count = MagicLinkSession.objects.filter(
            form_config=form_config
        ).count()
        completed_count = MagicLinkSession.objects.filter(
            form_config=form_config, completion_status="completed"
        ).count()

        completion_rate = (
            (completed_count / sessions_count * 100)
            if sessions_count > 0
            else 0
        )

        form_stats.append(
            {
                "form": form_config,
                "total_sessions": sessions_count,
                "completed_sessions": completed_count,
                "completion_rate": round(completion_rate, 1),
            }
        )

    context = {
        "total_forms": total_forms,
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "completed_sessions": completed_sessions,
        "completion_rate": round(
            (
                (completed_sessions / total_sessions * 100)
                if total_sessions > 0
                else 0
            ),
            1,
        ),
        "recent_sessions": recent_sessions,
        "form_stats": sorted(
            form_stats, key=lambda x: x["total_sessions"], reverse=True
        ),
    }

    return render(request, "voice_flow/analytics_dashboard.html", context)
