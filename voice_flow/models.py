"""
Models for Voice Flow Service
"""
import secrets
import hashlib
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


def generate_api_key():
    """Generate a secure API key"""
    return f"vf_{secrets.token_urlsafe(32)}"


def generate_webhook_secret():
    """Generate a secure webhook secret"""
    return f"wh_{secrets.token_urlsafe(32)}"


def generate_form_id():
    """Generate a unique form ID"""
    return f"f_{secrets.token_urlsafe(12)}"


def generate_session_id():
    """Generate a unique session ID"""
    return f"s_{secrets.token_urlsafe(12)}"


class APIKey(models.Model):
    """API Key for authentication"""
    key = models.CharField(max_length=128, unique=True, default=generate_api_key)
    name = models.CharField(max_length=255, help_text="Descriptive name for this API key")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.key[:10]}...)"
    
    def mark_used(self):
        """Mark this API key as used"""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class VoiceFormConfig(models.Model):
    """Configuration for a voice form"""
    form_id = models.CharField(max_length=50, unique=True, default=generate_form_id, primary_key=True)
    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='forms')
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Form Configuration
    fields = models.JSONField(help_text="Array of field definitions")
    ai_prompt = models.TextField(help_text="Initial AI prompt for the conversation")
    
    # Callback Configuration
    callback_url = models.URLField(help_text="Webhook URL to send completed data")
    callback_method = models.CharField(max_length=10, default='POST', choices=[('POST', 'POST'), ('PUT', 'PUT')])
    webhook_secret = models.CharField(max_length=128, default=generate_webhook_secret)
    
    # Messages
    success_message = models.TextField(default="Thank you for completing the form!")
    error_message = models.TextField(default="We encountered an error. Please try again.")
    
    # Settings
    settings = models.JSONField(default=dict, help_text="Additional form settings")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.form_id})"
    
    def get_magic_link(self, domain_url):
        """Get the base magic link for this form"""
        return f"{domain_url}/f/{self.form_id}"


class MagicLinkSession(models.Model):
    """Individual session for a magic link"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('error', 'Error'),
    ]
    
    session_id = models.CharField(max_length=50, unique=True, default=generate_session_id, primary_key=True)
    form_config = models.ForeignKey(VoiceFormConfig, on_delete=models.CASCADE, related_name='sessions')
    
    # Session Data
    session_data = models.JSONField(default=dict, help_text="Custom data passed during link generation")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Collected Data
    collected_data = models.JSONField(default=dict, help_text="Data collected during the session")
    conversation_history = models.JSONField(default=list, help_text="Full conversation transcript")
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    duration_seconds = models.IntegerField(null=True, blank=True)
    fields_completed = models.IntegerField(default=0)
    total_interactions = models.IntegerField(default=0)
    retry_count = models.IntegerField(default=0)
    
    # Webhook Status
    webhook_sent = models.BooleanField(default=False)
    webhook_response_code = models.IntegerField(null=True, blank=True)
    webhook_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['form_config', 'status']),
        ]
    
    def __str__(self):
        return f"Session {self.session_id} - {self.status}"
    
    def is_expired(self):
        """Check if session is expired"""
        return timezone.now() > self.expires_at
    
    def get_magic_link(self, domain_url):
        """Get the magic link URL for this session"""
        return f"{domain_url}/s/{self.session_id}"
    
    def mark_started(self):
        """Mark session as started"""
        if self.status == 'pending':
            self.status = 'active'
            self.started_at = timezone.now()
            self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self):
        """Mark session as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.completed_at - self.started_at).total_seconds())
        self.save(update_fields=['status', 'completed_at', 'duration_seconds'])
    
    def add_conversation_message(self, role, content, field_name=None):
        """Add a message to conversation history"""
        message = {
            'role': role,
            'content': content,
            'timestamp': timezone.now().isoformat(),
        }
        if field_name:
            message['field_name'] = field_name
        
        self.conversation_history.append(message)
        self.total_interactions += 1
        self.save(update_fields=['conversation_history', 'total_interactions'])
    
    def update_collected_data(self, field_name, value):
        """Update collected data for a field"""
        self.collected_data[field_name] = value
        self.fields_completed = len([v for v in self.collected_data.values() if v is not None])
        self.save(update_fields=['collected_data', 'fields_completed'])
    
    def get_completion_percentage(self):
        """Calculate completion percentage"""
        total_fields = len(self.form_config.fields)
        if total_fields == 0:
            return 0
        return int((self.fields_completed / total_fields) * 100)


class WebhookLog(models.Model):
    """Log of webhook delivery attempts"""
    session = models.ForeignKey(MagicLinkSession, on_delete=models.CASCADE, related_name='webhook_logs')
    
    # Request Info
    url = models.URLField()
    method = models.CharField(max_length=10)
    payload = models.JSONField()
    headers = models.JSONField(default=dict)
    
    # Response Info
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    
    # Retry Info
    attempt_number = models.IntegerField(default=1)
    is_success = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]
    
    def __str__(self):
        return f"Webhook {self.method} to {self.url} - {self.status_code}"

