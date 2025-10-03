from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import callback_views, config_views, magic_link_views, sdk_views, views

# Create router for API endpoints
router = DefaultRouter()
router.register(r"form-configurations", views.FormConfigurationViewSet)
router.register(r"magic-link-sessions", views.MagicLinkSessionViewSet)
router.register(r"form-data", views.DynamicFormDataViewSet)
router.register(r"form-submissions", views.FormSubmissionViewSet)

urlpatterns = [
    # Web interface
    path("", views.home, name="home"),
    path("voice/", views.voice_interface, name="voice_interface"),
    path(
        "voice/<str:session_id>/", views.voice_interface, name="voice_session"
    ),
    # Configuration interface
    path("config/", config_views.config_dashboard, name="config_dashboard"),
    path("config/forms/", config_views.create_form, name="create_form"),
    path(
        "config/forms/<uuid:form_id>/",
        config_views.form_detail,
        name="form_detail",
    ),
    path(
        "config/forms/<uuid:form_id>/update/",
        config_views.update_form_config,
        name="update_form_config",
    ),
    path(
        "config/forms/<uuid:form_id>/delete/",
        config_views.delete_form_config,
        name="delete_form_config",
    ),
    path(
        "config/forms/<uuid:form_id>/magic-link/",
        config_views.generate_magic_link,
        name="generate_magic_link",
    ),
    path(
        "config/sessions/<uuid:session_id>/",
        config_views.session_detail,
        name="session_detail",
    ),
    path(
        "config/builder/",
        config_views.FormBuilderView.as_view(),
        name="form_builder",
    ),
    path(
        "config/analytics/",
        config_views.analytics_dashboard,
        name="analytics_dashboard",
    ),
    # Magic link interface
    path(
        "voice/magic/<str:magic_link_id>/",
        magic_link_views.magic_link_access,
        name="magic_link_access",
    ),
    path(
        "voice/magic/<str:magic_link_id>/submit/",
        magic_link_views.magic_link_submit,
        name="magic_link_submit",
    ),
    path(
        "voice/magic/<str:magic_link_id>/status/",
        magic_link_views.magic_link_status,
        name="magic_link_status",
    ),
    path(
        "voice/magic/<str:magic_link_id>/embed/",
        magic_link_views.magic_link_embed,
        name="magic_link_embed",
    ),
    path(
        "voice/magic/<str:magic_link_id>/qr/",
        magic_link_views.magic_link_qr_code,
        name="magic_link_qr",
    ),
    path(
        "voice/magic/<str:magic_link_id>/test-webhook/",
        magic_link_views.magic_link_webhook_test,
        name="magic_link_webhook_test",
    ),
    # SDK endpoints
    path("api/sdk/", sdk_views.SDKStatusView.as_view(), name="sdk_status"),
    path(
        "api/sdk/forms/",
        sdk_views.SDKFormManagementView.as_view(),
        name="sdk_forms",
    ),
    path(
        "api/sdk/magic-link/",
        sdk_views.SDKMagicLinkView.as_view(),
        name="sdk_magic_link",
    ),
    path(
        "api/sdk/form-data/<uuid:session_id>/",
        sdk_views.SDKFormDataView.as_view(),
        name="sdk_form_data",
    ),
    path(
        "api/sdk/test-webhook/",
        sdk_views.test_webhook,
        name="sdk_test_webhook",
    ),
    path(
        "api/sdk/quick-start/",
        sdk_views.SDKQuickStartView.as_view(),
        name="sdk_quick_start",
    ),
    # Callback endpoints
    path(
        "api/webhook/<uuid:form_id>/",
        callback_views.webhook_callback,
        name="webhook_callback",
    ),
    path(
        "api/webhook/retry/<uuid:submission_id>/",
        callback_views.retry_callback,
        name="retry_callback",
    ),
    path(
        "api/webhook/status/<uuid:session_id>/",
        callback_views.CallbackStatusView.as_view(),
        name="callback_status",
    ),
    path(
        "api/webhook/test/",
        callback_views.WebhookTestView.as_view(),
        name="webhook_test",
    ),
    # API endpoints
    path("api/", include(router.urls)),
    path(
        "api/sdk/", views.SDKIntegrationView.as_view(), name="sdk_integration"
    ),
]
