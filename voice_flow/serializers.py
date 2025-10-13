"""
Serializers for Voice Flow API
"""
from rest_framework import serializers
from .models import VoiceFormConfig, MagicLinkSession, APIKey
from datetime import timedelta
from django.utils import timezone


class FieldValidationSerializer(serializers.Serializer):
    """Validation rules for a field"""
    min_length = serializers.IntegerField(required=False)
    max_length = serializers.IntegerField(required=False)
    min = serializers.FloatField(required=False)
    max = serializers.FloatField(required=False)
    pattern = serializers.CharField(required=False)
    options = serializers.ListField(child=serializers.CharField(), required=False)
    min_date = serializers.DateField(required=False)
    max_date = serializers.DateField(required=False)
    format = serializers.CharField(required=False)
    integer_only = serializers.BooleanField(required=False)
    domain_whitelist = serializers.ListField(child=serializers.CharField(), required=False)
    domain_blacklist = serializers.ListField(child=serializers.CharField(), required=False)
    country_code = serializers.CharField(required=False)
    min_choices = serializers.IntegerField(required=False)
    max_choices = serializers.IntegerField(required=False)


class FieldSerializer(serializers.Serializer):
    """Serializer for form field definition"""
    FIELD_TYPE_CHOICES = ['text', 'number', 'email', 'phone', 'date', 'boolean', 'choice', 'multi_choice']
    
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=FIELD_TYPE_CHOICES)
    required = serializers.BooleanField(default=False)
    prompt = serializers.CharField()
    validation = FieldValidationSerializer(required=False)
    
    def validate_name(self, value):
        """Validate field name"""
        if not value.replace('_', '').isalnum():
            raise serializers.ValidationError("Field name must be alphanumeric with underscores only")
        return value


class FormSettingsSerializer(serializers.Serializer):
    """Serializer for form settings"""
    max_duration_minutes = serializers.IntegerField(default=10, min_value=1, max_value=60)
    language = serializers.CharField(default='en-US')
    voice_style = serializers.CharField(default='friendly')
    allow_interruptions = serializers.BooleanField(default=True)


class VoiceFormConfigSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating voice form configuration"""
    fields = FieldSerializer(many=True)
    settings = FormSettingsSerializer(required=False)
    magic_link = serializers.SerializerMethodField()
    webhook_secret = serializers.CharField(read_only=True)
    
    class Meta:
        model = VoiceFormConfig
        fields = [
            'form_id', 'name', 'description', 'fields', 'ai_prompt',
            'callback_url', 'callback_method', 'webhook_secret',
            'success_message', 'error_message', 'settings',
            'magic_link', 'created_at', 'is_active'
        ]
        read_only_fields = ['form_id', 'webhook_secret', 'created_at']
    
    def get_magic_link(self, obj):
        """Get the magic link URL"""
        request = self.context.get('request')
        if request:
            domain = f"{request.scheme}://{request.get_host()}"
            return obj.get_magic_link(domain)
        return None
    
    def validate_fields(self, value):
        """Validate fields array"""
        if not value:
            raise serializers.ValidationError("At least one field is required")
        
        if len(value) > 50:
            raise serializers.ValidationError("Maximum 50 fields allowed")
        
        # Check for duplicate field names
        field_names = [field['name'] for field in value]
        if len(field_names) != len(set(field_names)):
            raise serializers.ValidationError("Duplicate field names are not allowed")
        
        return value
    
    def create(self, validated_data):
        """Create a new form configuration"""
        api_key = self.context['request'].auth
        validated_data['api_key'] = api_key
        return super().create(validated_data)


class GenerateSessionLinkSerializer(serializers.Serializer):
    """Serializer for generating a session link"""
    session_data = serializers.JSONField(default=dict)
    expires_in_hours = serializers.IntegerField(default=24, min_value=1, max_value=720)  # Max 30 days


class MagicLinkSessionSerializer(serializers.ModelSerializer):
    """Serializer for magic link session"""
    magic_link = serializers.SerializerMethodField()
    form_name = serializers.CharField(source='form_config.name', read_only=True)
    completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = MagicLinkSession
        fields = [
            'session_id', 'form_name', 'status', 'magic_link',
            'session_data', 'collected_data', 'completion_percentage',
            'created_at', 'expires_at', 'started_at', 'completed_at',
            'duration_seconds', 'fields_completed', 'total_interactions'
        ]
        read_only_fields = [
            'session_id', 'status', 'collected_data', 'created_at',
            'started_at', 'completed_at', 'duration_seconds',
            'fields_completed', 'total_interactions'
        ]
    
    def get_magic_link(self, obj):
        """Get the magic link URL"""
        request = self.context.get('request')
        if request:
            domain = f"{request.scheme}://{request.get_host()}"
            return obj.get_magic_link(domain)
        return None
    
    def get_completion_percentage(self, obj):
        """Get completion percentage"""
        return obj.get_completion_percentage()


class WebhookPayloadSerializer(serializers.Serializer):
    """Serializer for webhook payload"""
    form_id = serializers.CharField()
    session_id = serializers.CharField()
    completed_at = serializers.DateTimeField()
    data = serializers.JSONField()
    metadata = serializers.JSONField()


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API Key"""
    
    class Meta:
        model = APIKey
        fields = ['key', 'name', 'created_at', 'last_used_at', 'is_active']
        read_only_fields = ['key', 'created_at', 'last_used_at']

