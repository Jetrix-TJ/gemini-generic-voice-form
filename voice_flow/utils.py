import json
import logging
from typing import Any, Dict, List

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)


def save_form_field(
    session_id: str, field_name: str, field_value: Any
) -> Dict[str, Any]:
    """
    Function tool for Gemini to save form field data

    Args:
        session_id: UUID of the magic link session
        field_name: Name of the field to save
        field_value: Value to save

    Returns:
        Dict with success status and message
    """
    try:
        from .models import DynamicFormData, MagicLinkSession

        session = MagicLinkSession.objects.get(id=session_id)

        # Save or update the field data
        DynamicFormData.objects.update_or_create(
            session=session,
            field_name=field_name,
            defaults={
                "field_value": str(field_value),
                "field_type": "voice_input",
            },
        )

        # Update session data
        session.session_data[field_name] = field_value
        session.save()

        return {
            "success": True,
            "message": f"Successfully saved {field_name}",
            "field_name": field_name,
            "field_value": field_value,
        }

    except MagicLinkSession.DoesNotExist:
        return {"success": False, "message": f"Session {session_id} not found"}
    except Exception as e:
        logger.error(f"Error saving field {field_name}: {str(e)}")
        return {
            "success": False,
            "message": f"Error saving {field_name}: {str(e)}",
        }


def get_checklist_status(appointment) -> Dict[str, Any]:
    """
    Get the current completion status of the appointment checklist

    Args:
        appointment: Appointment instance

    Returns:
        Dict with checklist status and progress
    """
    checklist_sections = {
        "patient_info": {
            "title": "Patient Information",
            "fields": [
                "first_name",
                "last_name",
                "date_of_birth",
                "phone",
                "email",
            ],
            "completed": 0,
            "total": 5,
            "status": "pending",
        },
        "contact_info": {
            "title": "Contact Information",
            "fields": [
                "address",
                "city",
                "state",
                "zip_code",
                "emergency_contact_name",
            ],
            "completed": 0,
            "total": 5,
            "status": "pending",
        },
        "visit_context": {
            "title": "Visit Context",
            "fields": ["visit_type", "reason_for_visit", "insurance_provider"],
            "completed": 0,
            "total": 3,
            "status": "pending",
        },
        "medical_info": {
            "title": "Medical Information",
            "fields": [
                "current_symptoms",
                "medications",
                "allergies",
                "medical_history",
            ],
            "completed": 0,
            "total": 4,
            "status": "pending",
        },
        "consent": {
            "title": "Consent & Communication",
            "fields": [
                "consent_to_treatment",
                "consent_to_billing",
                "consent_to_communication",
            ],
            "completed": 0,
            "total": 3,
            "status": "pending",
        },
    }

    total_completed = 0
    total_fields = 0

    for section_key, section in checklist_sections.items():
        completed_count = 0
        for field in section["fields"]:
            field_value = getattr(appointment, field, None)
            if field_value and str(field_value).strip():
                completed_count += 1
                total_completed += 1
            total_fields += 1

        section["completed"] = completed_count
        section["status"] = (
            "completed"
            if completed_count == section["total"]
            else "in_progress" if completed_count > 0 else "pending"
        )

    overall_progress = (
        (total_completed / total_fields * 100) if total_fields > 0 else 0
    )

    return {
        "sections": checklist_sections,
        "overall_progress": round(overall_progress, 1),
        "total_completed": total_completed,
        "total_fields": total_fields,
        "is_complete": appointment.is_complete,
    }


def format_validation_error(field_name: str, error_message: str) -> str:
    """
    Format validation error messages for user-friendly display

    Args:
        field_name: Name of the field with error
        error_message: Original error message

    Returns:
        Formatted error message
    """
    field_display_names = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "date_of_birth": "Date of Birth",
        "phone": "Phone Number",
        "email": "Email Address",
        "ssn": "Social Security Number",
        "zip_code": "ZIP Code",
    }

    display_name = field_display_names.get(
        field_name, field_name.replace("_", " ").title()
    )

    return f"{display_name}: {error_message}"


def validate_patient_data(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Validate patient data and return formatted errors

    Args:
        data: Dictionary of patient data

    Returns:
        Dict with field names as keys and error messages as values
    """
    errors = {}

    # Required field validation
    required_fields = {
        "first_name": "First name is required",
        "last_name": "Last name is required",
        "date_of_birth": "Date of birth is required",
        "phone": "Phone number is required",
        "reason_for_visit": "Reason for visit is required",
    }

    for field, message in required_fields.items():
        if not data.get(field) or not str(data[field]).strip():
            errors[field] = [message]

    # Format validation
    if data.get("email") and "@" not in str(data["email"]):
        errors["email"] = ["Please enter a valid email address"]

    if (
        data.get("phone")
        and len(
            str(data["phone"])
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .replace(" ", "")
        )
        < 10
    ):
        errors["phone"] = ["Please enter a valid phone number"]

    return errors


def get_next_incomplete_field(appointment) -> str:
    """
    Determine the next field that needs to be completed

    Args:
        appointment: Appointment instance

    Returns:
        Name of the next field to complete
    """
    field_priority = [
        "first_name",
        "last_name",
        "date_of_birth",
        "phone",
        "email",
        "address",
        "city",
        "state",
        "zip_code",
        "emergency_contact_name",
        "visit_type",
        "reason_for_visit",
        "insurance_provider",
        "current_symptoms",
        "medications",
        "allergies",
        "medical_history",
        "consent_to_treatment",
        "consent_to_billing",
        "consent_to_communication",
    ]

    for field in field_priority:
        field_value = getattr(appointment, field, None)
        if not field_value or not str(field_value).strip():
            return field

    return None


def generate_conversation_context(appointment) -> str:
    """
    Generate context string for Gemini conversation

    Args:
        appointment: Appointment instance

    Returns:
        Context string for the conversation
    """
    context_parts = []

    if appointment.first_name and appointment.last_name:
        context_parts.append(f"Patient: {appointment.full_name}")

    if appointment.date_of_birth:
        context_parts.append(f"Date of Birth: {appointment.date_of_birth}")

    if appointment.phone:
        context_parts.append(f"Phone: {appointment.phone}")

    if appointment.reason_for_visit:
        context_parts.append(
            f"Reason for Visit: {appointment.reason_for_visit}"
        )

    if appointment.visit_type:
        context_parts.append(f"Visit Type: {appointment.visit_type}")

    # Add progress information
    checklist = get_checklist_status(appointment)
    context_parts.append(
        f"Progress: {checklist['overall_progress']}% complete"
    )

    # Add next field to complete
    next_field = get_next_incomplete_field(appointment)
    if next_field:
        context_parts.append(f"Next field to collect: {next_field}")

    return (
        " | ".join(context_parts)
        if context_parts
        else "New patient intake session"
    )


def create_gemini_function_tool():
    """
    Create the function tool definition for Gemini

    Returns:
        Function tool definition
    """
    return {
        "function_declarations": [
            {
                "name": "save_form_field",
                "description": "Save a form field value to the session record",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The UUID of the magic link session",
                        },
                        "field_name": {
                            "type": "string",
                            "description": "The name of the field to save",
                        },
                        "field_value": {
                            "type": "string",
                            "description": "The value to save for the field",
                        },
                    },
                    "required": ["session_id", "field_name", "field_value"],
                },
            }
        ]
    }
