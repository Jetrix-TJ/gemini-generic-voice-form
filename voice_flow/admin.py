"""
Admin configuration for Voice Flow models
"""
from django.contrib import admin
from .models import APIKey, VoiceFormConfig, MagicLinkSession, WebhookLog


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'key_preview', 'user', 'created_at', 'last_used_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'key', 'user__username']
    readonly_fields = ['key', 'created_at', 'last_used_at']
    
    def key_preview(self, obj):
        return f"{obj.key[:15]}..."
    key_preview.short_description = 'API Key'


@admin.register(VoiceFormConfig)
class VoiceFormConfigAdmin(admin.ModelAdmin):
    list_display = ['form_id', 'name', 'api_key', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['form_id', 'name', 'description']
    readonly_fields = ['form_id', 'webhook_secret', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('form_id', 'api_key', 'name', 'description', 'is_active')
        }),
        ('Form Configuration', {
            'fields': ('fields', 'ai_prompt', 'settings')
        }),
        ('Callback Configuration', {
            'fields': ('callback_url', 'callback_method', 'webhook_secret')
        }),
        ('Messages', {
            'fields': ('success_message', 'error_message')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MagicLinkSession)
class MagicLinkSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'form_config', 'status', 'created_at', 'completed_at', 'webhook_sent']
    list_filter = ['status', 'webhook_sent', 'created_at']
    search_fields = ['session_id', 'form_config__name']
    readonly_fields = [
        'session_id', 'created_at', 'started_at', 'completed_at',
        'duration_seconds', 'total_interactions', 'webhook_sent_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': ('session_id', 'form_config', 'status')
        }),
        ('Session Data', {
            'fields': ('session_data', 'collected_data', 'conversation_history')
        }),
        ('Timing', {
            'fields': ('created_at', 'expires_at', 'started_at', 'completed_at', 'duration_seconds')
        }),
        ('Metrics', {
            'fields': ('fields_completed', 'total_interactions', 'retry_count')
        }),
        ('Webhook', {
            'fields': ('webhook_sent', 'webhook_response_code', 'webhook_sent_at')
        }),
    )


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ['session', 'method', 'url', 'status_code', 'is_success', 'attempt_number', 'created_at']
    list_filter = ['is_success', 'method', 'created_at']
    search_fields = ['session__session_id', 'url']
    readonly_fields = ['created_at', 'response_time_ms']

