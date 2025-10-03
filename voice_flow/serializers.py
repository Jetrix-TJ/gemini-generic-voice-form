from rest_framework import serializers

from .models import (
    DynamicFormData,
    FormConfiguration,
    FormSubmission,
    MagicLinkSession,
)


class FormConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for FormConfiguration model"""

    class Meta:
        model = FormConfiguration
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class MagicLinkSessionSerializer(serializers.ModelSerializer):
    """Serializer for MagicLinkSession model"""

    form_config = FormConfigurationSerializer(read_only=True)

    class Meta:
        model = MagicLinkSession
        fields = "__all__"
        read_only_fields = ["id", "created_at", "last_activity", "expires_at"]


class DynamicFormDataSerializer(serializers.ModelSerializer):
    """Serializer for DynamicFormData model"""

    class Meta:
        model = DynamicFormData
        fields = "__all__"
        read_only_fields = ["id", "collected_at"]


class FormSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for FormSubmission model"""

    session = MagicLinkSessionSerializer(read_only=True)

    class Meta:
        model = FormSubmission
        fields = "__all__"
        read_only_fields = ["id", "submission_timestamp"]
