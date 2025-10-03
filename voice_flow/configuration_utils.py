"""
Dynamic form configuration utilities
Allows users to configure forms without touching backend code
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings


class FormConfigBuilder:
    """
    Builder class for creating form configurations
    """

    def __init__(self, name: str, description: str = ""):
        self.config = {
            "name": name,
            "description": description,
            "sections": [],
            "validation_rules": {},
            "ai_instructions": "You are a professional assistant helping to collect information. Be friendly, clear, and ask one question at a time.",
            "callback_settings": {
                "enabled": True,
                "retry_attempts": 3,
                "retry_delay": 5,
            },
        }

    def add_section(
        self, title: str, description: str = ""
    ) -> "FormConfigBuilder":
        """Add a new section to the form"""
        section = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "fields": [],
            "order": len(self.config["sections"]),
        }
        self.config["sections"].append(section)
        return self

    def add_field(
        self, section_id: str, field_config: Dict[str, Any]
    ) -> "FormConfigBuilder":
        """Add a field to a specific section"""
        # Find section by id or use the last section
        if section_id:
            section = next(
                (s for s in self.config["sections"] if s["id"] == section_id),
                None,
            )
        else:
            section = (
                self.config["sections"][-1]
                if self.config["sections"]
                else None
            )

        if not section:
            raise ValueError(f"Section {section_id} not found")

        field = {
            "id": str(uuid.uuid4()),
            "name": field_config["name"],
            "label": field_config.get(
                "label", field_config["name"].replace("_", " ").title()
            ),
            "type": field_config.get("type", "text"),
            "required": field_config.get("required", False),
            "placeholder": field_config.get("placeholder", ""),
            "validation": field_config.get("validation", {}),
            "ai_prompt": field_config.get("ai_prompt", ""),
            "order": len(section["fields"]),
        }

        # Add field-specific configuration
        if field_config.get("type") == "select":
            field["options"] = field_config.get("options", [])
        elif field_config.get("type") == "file":
            field["allowed_types"] = field_config.get(
                "allowed_types", ["image/*", "application/pdf"]
            )
            field["max_size"] = field_config.get("max_size", 10485760)  # 10MB

        section["fields"].append(field)
        return self

    def set_ai_instructions(self, instructions: str) -> "FormConfigBuilder":
        """Set custom AI instructions"""
        self.config["ai_instructions"] = instructions
        return self

    def set_callback_url(
        self, url: str, headers: Dict = None, secret: str = None
    ) -> "FormConfigBuilder":
        """Set callback URL for form submissions"""
        self.config["callback_settings"]["url"] = url
        if headers:
            self.config["callback_settings"]["headers"] = headers
        if secret:
            self.config["callback_settings"]["secret"] = secret
        return self

    def set_validation_rule(
        self, field_name: str, rule: Dict[str, Any]
    ) -> "FormConfigBuilder":
        """Set validation rules for a field"""
        self.config["validation_rules"][field_name] = rule
        return self

    def build(self) -> Dict[str, Any]:
        """Build the final configuration"""
        return self.config


class MagicLinkGenerator:
    """
    Generate magic links for form access
    """

    @staticmethod
    def create_magic_link(
        form_config_id: str, expiry_hours: int = 24, custom_data: Dict = None
    ) -> str:
        """Create a magic link for form access"""
        from django.utils import timezone

        from .models import FormConfiguration, MagicLinkSession

        # Get form configuration
        form_config = FormConfiguration.objects.get(id=form_config_id)

        # Create magic link session
        magic_link_id = str(uuid.uuid4())
        expires_at = timezone.now() + timedelta(hours=expiry_hours)

        session = MagicLinkSession.objects.create(
            form_config=form_config,
            magic_link_id=magic_link_id,
            expires_at=expires_at,
            session_data=custom_data or {},
        )

        # Generate magic link URL
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        magic_link = f"{base_url}/voice/magic/{magic_link_id}/"

        return magic_link

    @staticmethod
    def validate_magic_link(
        magic_link_id: str,
    ) -> Optional["MagicLinkSession"]:
        """Validate and return magic link session"""
        from .models import MagicLinkSession

        try:
            session = MagicLinkSession.objects.get(
                magic_link_id=magic_link_id, completion_status="active"
            )

            if session.is_expired:
                session.completion_status = "expired"
                session.save()
                return None

            return session
        except MagicLinkSession.DoesNotExist:
            return None


class CallbackDelivery:
    """
    Handle callback delivery to external URLs
    """

    @staticmethod
    def deliver_form_data(
        session: "MagicLinkSession", form_data: Dict[str, Any]
    ) -> bool:
        """Deliver form data to callback URL"""
        from .models import FormSubmission
        
        try:
            callback_settings = session.form_config.form_schema.get(
                "callback_settings", {}
            )

            if not callback_settings.get("enabled", True):
                return True  # No callback needed

            callback_url = callback_settings.get("url")
            if not callback_url:
                return True  # No callback URL set

            # Prepare callback payload
            payload = {
                "form_id": str(session.form_config.id),
                "form_name": session.form_config.name,
                "session_id": str(session.id),
                "magic_link_id": session.magic_link_id,
                "submission_timestamp": datetime.now().isoformat(),
                "form_data": form_data,
                "completion_status": session.completion_status,
            }

            # Add custom headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "VoiceFlow-Callback/1.0",
            }
            headers.update(callback_settings.get("headers", {}))

            # Add authentication if secret is provided
            if callback_settings.get("secret"):
                signature = CallbackDelivery._generate_signature(
                    payload, callback_settings["secret"]
                )
                headers["X-Signature"] = signature

            # Make callback request
            response = requests.post(
                callback_url, json=payload, headers=headers, timeout=30
            )

            # Create submission record
            FormSubmission.objects.create(
                session=session,
                submitted_data=payload,
                callback_delivered=response.status_code == 200,
                callback_response_code=response.status_code,
                callback_response_body=response.text[
                    :1000
                ],  # Limit response body
            )

            return response.status_code == 200

        except Exception as e:
            # Log error and create failed submission record
            FormSubmission.objects.create(
                session=session,
                submitted_data=form_data,
                callback_delivered=False,
                callback_response_body=str(e)[:1000],
            )
            return False

    @staticmethod
    def _generate_signature(payload: Dict, secret: str) -> str:
        """Generate HMAC signature for callback authentication"""
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode("utf-8"), payload_str.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"


class FormValidator:
    """
    Validate form data against configuration
    """

    @staticmethod
    def validate_field_data(field_config: Dict, value: Any) -> Dict[str, Any]:
        """Validate a single field against its configuration"""
        errors = []

        # Required field validation
        if field_config.get("required", False) and not value:
            errors.append(
                f"{field_config.get('label', field_config['name'])} is required"
            )

        # Type-specific validation
        field_type = field_config.get("type", "text")

        if field_type == "email" and value:
            import re

            if not re.match(
                r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value
            ):
                errors.append("Invalid email format")

        elif field_type == "phone" and value:
            import re

            phone_digits = re.sub(r"\D", "", value)
            if len(phone_digits) < 10:
                errors.append("Invalid phone number format")

        elif field_type == "number" and value:
            try:
                float(value)
            except ValueError:
                errors.append("Must be a valid number")

        # Custom validation rules
        validation_rules = field_config.get("validation", {})
        if (
            validation_rules.get("min_length")
            and len(str(value)) < validation_rules["min_length"]
        ):
            errors.append(
                f"Minimum length is {validation_rules['min_length']} characters"
            )

        if (
            validation_rules.get("max_length")
            and len(str(value)) > validation_rules["max_length"]
        ):
            errors.append(
                f"Maximum length is {validation_rules['max_length']} characters"
            )

        return {"valid": len(errors) == 0, "errors": errors}

    @staticmethod
    def validate_form_data(
        form_schema: Dict, form_data: Dict
    ) -> Dict[str, Any]:
        """Validate entire form data against schema"""
        all_errors = {}
        is_valid = True

        # Collect all fields from sections
        all_fields = {}
        for section in form_schema.get("sections", []):
            for field in section.get("fields", []):
                all_fields[field["name"]] = field

        # Validate each field
        for field_name, field_config in all_fields.items():
            value = form_data.get(field_name, "")
            validation_result = FormValidator.validate_field_data(
                field_config, value
            )

            if not validation_result["valid"]:
                all_errors[field_name] = validation_result["errors"]
                is_valid = False

        return {"valid": is_valid, "errors": all_errors}


# Pre-built form configurations
class PreBuiltForms:
    """
    Pre-built form configurations for common use cases
    """

    @staticmethod
    def patient_intake_form() -> Dict[str, Any]:
        """Pre-built patient intake form"""
        builder = FormConfigBuilder(
            name="Patient Intake Form",
            description="Comprehensive patient registration and medical history collection",
        )

        # Personal Information Section
        builder.add_section("Personal Information", "Basic patient details")
        builder.add_field(
            None,
            {
                "name": "first_name",
                "label": "First Name",
                "type": "text",
                "required": True,
                "validation": {"min_length": 2, "max_length": 50},
            },
        )
        builder.add_field(
            None,
            {
                "name": "last_name",
                "label": "Last Name",
                "type": "text",
                "required": True,
                "validation": {"min_length": 2, "max_length": 50},
            },
        )
        builder.add_field(
            None,
            {
                "name": "date_of_birth",
                "label": "Date of Birth",
                "type": "date",
                "required": True,
            },
        )
        builder.add_field(
            None,
            {
                "name": "phone",
                "label": "Phone Number",
                "type": "phone",
                "required": True,
            },
        )
        builder.add_field(
            None, {"name": "email", "label": "Email Address", "type": "email"}
        )

        # Medical Information Section
        builder.add_section(
            "Medical Information", "Current symptoms and medical history"
        )
        builder.add_field(
            None,
            {
                "name": "current_symptoms",
                "label": "Current Symptoms",
                "type": "textarea",
                "required": True,
                "placeholder": "Describe your current symptoms in detail",
            },
        )
        builder.add_field(
            None,
            {
                "name": "medications",
                "label": "Current Medications",
                "type": "textarea",
                "placeholder": "List all current medications and dosages",
            },
        )
        builder.add_field(
            None,
            {
                "name": "allergies",
                "label": "Allergies",
                "type": "textarea",
                "placeholder": "List any known allergies",
            },
        )

        # Insurance Section
        builder.add_section(
            "Insurance Information", "Insurance and billing details"
        )
        builder.add_field(
            None,
            {
                "name": "insurance_provider",
                "label": "Insurance Provider",
                "type": "text",
            },
        )
        builder.add_field(
            None,
            {
                "name": "policy_number",
                "label": "Policy Number",
                "type": "text",
            },
        )

        return builder.build()

    @staticmethod
    def contact_form() -> Dict[str, Any]:
        """Pre-built contact form"""
        builder = FormConfigBuilder(
            name="Contact Form",
            description="Simple contact information collection",
        )

        builder.add_section("Contact Information", "How can we help you?")
        builder.add_field(
            None,
            {
                "name": "name",
                "label": "Full Name",
                "type": "text",
                "required": True,
            },
        )
        builder.add_field(
            None,
            {
                "name": "email",
                "label": "Email Address",
                "type": "email",
                "required": True,
            },
        )
        builder.add_field(
            None, {"name": "phone", "label": "Phone Number", "type": "phone"}
        )
        builder.add_field(
            None,
            {
                "name": "message",
                "label": "Message",
                "type": "textarea",
                "required": True,
                "placeholder": "Tell us how we can help you",
            },
        )

        return builder.build()

    @staticmethod
    def job_application_form() -> Dict[str, Any]:
        """Pre-built job application form"""
        builder = FormConfigBuilder(
            name="Job Application Form",
            description="Employment application and candidate information",
        )

        # Personal Information
        builder.add_section("Personal Information", "Basic candidate details")
        builder.add_field(
            None,
            {
                "name": "full_name",
                "label": "Full Name",
                "type": "text",
                "required": True,
            },
        )
        builder.add_field(
            None,
            {
                "name": "email",
                "label": "Email Address",
                "type": "email",
                "required": True,
            },
        )
        builder.add_field(
            None,
            {
                "name": "phone",
                "label": "Phone Number",
                "type": "phone",
                "required": True,
            },
        )

        # Professional Information
        builder.add_section(
            "Professional Information", "Work experience and qualifications"
        )
        builder.add_field(
            None,
            {
                "name": "current_position",
                "label": "Current Position",
                "type": "text",
            },
        )
        builder.add_field(
            None,
            {
                "name": "years_experience",
                "label": "Years of Experience",
                "type": "number",
            },
        )
        builder.add_field(
            None,
            {
                "name": "education",
                "label": "Education",
                "type": "textarea",
                "placeholder": "List your educational background",
            },
        )
        builder.add_field(
            None,
            {
                "name": "resume",
                "label": "Resume/CV",
                "type": "file",
                "allowed_types": ["application/pdf", "application/msword"],
                "max_size": 5242880,  # 5MB
            },
        )

        return builder.build()
