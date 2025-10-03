import json
import uuid

from django.core.validators import RegexValidator
from django.db import models


class FormConfiguration(models.Model):
    """
    Dynamic form configuration - no need to modify models!
    Users can create any form structure through JSON configuration
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # JSON configuration for the entire form structure
    form_schema = models.JSONField(default=dict)

    # Magic link settings
    magic_link_enabled = models.BooleanField(default=True)
    magic_link_expiry_hours = models.IntegerField(default=24)

    # Callback configuration
    callback_url = models.URLField(
        blank=True, help_text="URL to receive form data via POST"
    )
    callback_headers = models.JSONField(
        default=dict, blank=True, help_text="Custom headers for callback"
    )
    callback_secret = models.CharField(
        max_length=200,
        blank=True,
        help_text="Secret for callback authentication",
    )

    # AI Configuration
    ai_instructions = models.TextField(
        default="You are a professional assistant helping to collect information. Be friendly, clear, and ask one question at a time.",
        help_text="Custom instructions for the AI assistant",
    )
    ai_voice_name = models.CharField(max_length=50, default="Puck")
    ai_language = models.CharField(max_length=10, default="en-US")

    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.id}"

    @property
    def magic_link_url(self):
        """Generate magic link for this form"""
        return f"/voice/magic/{self.id}/"


class MagicLinkSession(models.Model):
    """
    Magic link sessions - track who accessed what form
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form_config = models.ForeignKey(
        FormConfiguration, on_delete=models.CASCADE, related_name="sessions"
    )
    magic_link_id = models.CharField(max_length=100, unique=True)

    # Session data
    session_data = models.JSONField(default=dict)
    conversation_history = models.JSONField(default=list)
    current_step = models.CharField(max_length=50, default="start")
    completion_status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("completed", "Completed"),
            ("expired", "Expired"),
            ("abandoned", "Abandoned"),
        ],
        default="active",
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    # Callback tracking
    callback_sent = models.BooleanField(default=False)
    callback_response = models.JSONField(default=dict, blank=True)
    callback_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Session {self.magic_link_id} - {self.form_config.name}"

    @property
    def is_expired(self):
        from django.utils import timezone

        return timezone.now() > self.expires_at


class DynamicFormData(models.Model):
    """
    Generic form data storage - stores any JSON data structure
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        MagicLinkSession, on_delete=models.CASCADE, related_name="form_data"
    )

    # Dynamic field storage
    field_name = models.CharField(max_length=100)
    field_value = models.TextField()  # Store as text, can be JSON
    field_type = models.CharField(max_length=50, default="text")

    # Metadata
    collected_at = models.DateTimeField(auto_now_add=True)
    ai_confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["collected_at"]
        unique_together = ["session", "field_name"]

    def __str__(self):
        return f"{self.session.magic_link_id} - {self.field_name}: {self.field_value[:50]}"


class FormSubmission(models.Model):
    """
    Track form submissions and callback deliveries
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(MagicLinkSession, on_delete=models.CASCADE)

    # Submission data
    submitted_data = models.JSONField()
    submission_timestamp = models.DateTimeField(auto_now_add=True)

    # Callback delivery
    callback_attempts = models.IntegerField(default=0)
    callback_delivered = models.BooleanField(default=False)
    callback_delivery_time = models.DateTimeField(null=True, blank=True)
    callback_response_code = models.IntegerField(null=True, blank=True)
    callback_response_body = models.TextField(blank=True)

    class Meta:
        ordering = ["-submission_timestamp"]

    def __str__(self):
        return f"Submission {self.id} - {self.session.form_config.name}"
