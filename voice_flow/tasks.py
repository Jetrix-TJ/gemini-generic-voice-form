"""
Celery tasks for background processing
"""
import json
import hmac
import hashlib
import logging
from datetime import datetime
from celery import shared_task
from django.utils import timezone
from django.conf import settings
import requests

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_webhook(self, session_id: str, attempt_number: int = 1):
    """
    Send webhook with completed form data
    
    Args:
        session_id: The session ID
        attempt_number: Current attempt number for retry tracking
    """
    from .models import MagicLinkSession, WebhookLog
    
    try:
        session = MagicLinkSession.objects.get(session_id=session_id)
        form_config = session.form_config
        
        # Prepare payload
        payload = {
            'form_id': form_config.form_id,
            'session_id': session.session_id,
            'completed_at': session.completed_at.isoformat() if session.completed_at else timezone.now().isoformat(),
            'data': session.collected_data,
            'metadata': {
                'duration_seconds': session.duration_seconds,
                'completion_percentage': session.get_completion_percentage(),
                'fields_completed': session.fields_completed,
                'total_fields': len(form_config.fields),
                'session_data': session.session_data,
                'conversation_metrics': {
                    'total_interactions': session.total_interactions,
                    'retry_count': session.retry_count,
                }
            }
        }
        
        # Generate signature
        signature = generate_webhook_signature(payload, form_config.webhook_secret)
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'X-VoiceForm-Signature': signature,
            'X-VoiceForm-Session-ID': session.session_id,
            'User-Agent': 'VoiceForms-Webhook/1.0'
        }
        
        # Send request
        webhook_timeout = settings.VOICE_FORM_SETTINGS.get('WEBHOOK_TIMEOUT', 30)
        start_time = datetime.now()
        
        response = requests.request(
            method=form_config.callback_method,
            url=form_config.callback_url,
            json=payload,
            headers=headers,
            timeout=webhook_timeout
        )
        
        response_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Log webhook
        webhook_log = WebhookLog.objects.create(
            session=session,
            url=form_config.callback_url,
            method=form_config.callback_method,
            payload=payload,
            headers=headers,
            status_code=response.status_code,
            response_body=response.text[:1000],  # Limit response body size
            response_time_ms=response_time_ms,
            attempt_number=attempt_number,
            is_success=response.status_code < 400
        )
        
        # Update session
        if response.status_code < 400:
            session.webhook_sent = True
            session.webhook_response_code = response.status_code
            session.webhook_sent_at = timezone.now()
            session.save(update_fields=['webhook_sent', 'webhook_response_code', 'webhook_sent_at'])
            
            logger.info(f"Webhook sent successfully for session {session_id}")
            return {
                'success': True,
                'status_code': response.status_code,
                'attempt': attempt_number
            }
        else:
            logger.warning(f"Webhook failed with status {response.status_code} for session {session_id}")
            raise Exception(f"Webhook returned status {response.status_code}")
    
    except Exception as exc:
        logger.error(f"Error sending webhook for session {session_id}: {exc}")
        
        # Log failed attempt
        try:
            WebhookLog.objects.create(
                session_id=session_id,
                url=form_config.callback_url if 'form_config' in locals() else 'unknown',
                method=form_config.callback_method if 'form_config' in locals() else 'POST',
                payload=payload if 'payload' in locals() else {},
                headers=headers if 'headers' in locals() else {},
                error_message=str(exc),
                attempt_number=attempt_number,
                is_success=False
            )
        except:
            pass
        
        # Retry logic
        max_retries = settings.VOICE_FORM_SETTINGS.get('WEBHOOK_RETRY_ATTEMPTS', 3)
        if attempt_number < max_retries:
            # Exponential backoff: 5min, 15min, 45min
            countdown = 300 * (3 ** (attempt_number - 1))
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error(f"Max retries reached for webhook session {session_id}")
            return {
                'success': False,
                'error': str(exc),
                'attempt': attempt_number
            }


def generate_webhook_signature(payload: dict, secret: str) -> str:
    """
    Generate HMAC signature for webhook payload
    
    Args:
        payload: The payload dictionary
        secret: The webhook secret
    
    Returns:
        Signature string in format 'sha256=<hex>'
    """
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"


@shared_task
def cleanup_expired_sessions():
    """
    Cleanup expired sessions that haven't been completed
    """
    from .models import MagicLinkSession
    
    cleanup_hours = settings.VOICE_FORM_SETTINGS.get('SESSION_CLEANUP_HOURS', 168)
    cutoff_time = timezone.now() - timezone.timedelta(hours=cleanup_hours)
    
    expired_sessions = MagicLinkSession.objects.filter(
        expires_at__lt=timezone.now(),
        status__in=['pending', 'active'],
        created_at__lt=cutoff_time
    )
    
    count = expired_sessions.count()
    expired_sessions.update(status='expired')
    
    logger.info(f"Marked {count} sessions as expired")
    
    return {'cleaned_up': count}

