from django.contrib import admin

from .models import (
    DynamicFormData,
    FormConfiguration,
    FormSubmission,
    MagicLinkSession,
)


@admin.register(FormConfiguration)
class FormConfigurationAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "created_at", "magic_link_enabled"]
    list_filter = ["is_active", "magic_link_enabled", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "description", "is_active")},
        ),
        (
            "Form Schema",
            {"fields": ("form_schema",), "classes": ("collapse",)},
        ),
        (
            "Magic Link Settings",
            {"fields": ("magic_link_enabled", "magic_link_expiry_hours")},
        ),
        (
            "Callback Configuration",
            {
                "fields": (
                    "callback_url",
                    "callback_headers",
                    "callback_secret",
                )
            },
        ),
        (
            "AI Configuration",
            {"fields": ("ai_instructions", "ai_voice_name", "ai_language")},
        ),
        (
            "System Information",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(MagicLinkSession)
class MagicLinkSessionAdmin(admin.ModelAdmin):
    list_display = [
        "magic_link_id",
        "form_config",
        "completion_status",
        "created_at",
        "expires_at",
    ]
    list_filter = ["completion_status", "created_at", "expires_at"]
    search_fields = ["magic_link_id", "form_config__name"]
    readonly_fields = ["id", "created_at", "last_activity", "expires_at"]
    fieldsets = (
        (
            "Session Information",
            {"fields": ("form_config", "magic_link_id", "completion_status")},
        ),
        (
            "Session Data",
            {
                "fields": ("session_data", "current_step"),
                "classes": ("collapse",),
            },
        ),
        (
            "Conversation History",
            {"fields": ("conversation_history",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "last_activity",
                    "expires_at",
                    "completed_at",
                )
            },
        ),
    )


@admin.register(DynamicFormData)
class DynamicFormDataAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "field_name",
        "field_value",
        "field_type",
        "collected_at",
    ]
    list_filter = ["field_type", "collected_at"]
    search_fields = ["session__magic_link_id", "field_name", "field_value"]
    readonly_fields = ["id", "collected_at"]


@admin.register(FormSubmission)
class FormSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "submission_timestamp",
        "callback_delivered",
        "callback_attempts",
    ]
    list_filter = ["callback_delivered", "submission_timestamp"]
    search_fields = ["session__magic_link_id", "session__form_config__name"]
    readonly_fields = ["id", "submission_timestamp"]
