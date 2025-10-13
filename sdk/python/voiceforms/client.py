"""
VoiceForms Python SDK Client
"""
import requests
from typing import Dict, List, Optional, Any
import json


class VoiceFormSDK:
    """
    Python SDK for VoiceForms API
    
    Example:
        sdk = VoiceFormSDK(api_key='your_api_key')
        form = sdk.create_form({
            'name': 'Customer Feedback',
            'fields': [...],
            'callback_url': 'https://your-app.com/webhook'
        })
        session = sdk.generate_session_link(form['form_id'])
    """
    
    def __init__(self, api_key: str, base_url: str = 'http://localhost:8000'):
        """
        Initialize VoiceForm SDK
        
        Args:
            api_key: Your API key
            base_url: Base URL of the VoiceForms API
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def create_form(self, config: Dict) -> Dict:
        """
        Create a new voice form configuration
        
        Args:
            config: Form configuration dictionary with fields:
                - name: Form name
                - description: Form description (optional)
                - fields: List of field definitions
                - ai_prompt: Initial AI prompt
                - callback_url: Webhook URL
                - callback_method: HTTP method (default: POST)
                - success_message: Success message (optional)
                - error_message: Error message (optional)
                - settings: Additional settings (optional)
        
        Returns:
            Dict with form_id, magic_link, webhook_secret, created_at
        """
        return self._request('POST', '/api/forms/', json=config)
    
    def get_form(self, form_id: str) -> Dict:
        """
        Get form configuration by ID
        
        Args:
            form_id: The form ID
        
        Returns:
            Form configuration dictionary
        """
        return self._request('GET', f'/api/forms/{form_id}/')
    
    def list_forms(self) -> List[Dict]:
        """
        List all forms
        
        Returns:
            List of form configurations
        """
        return self._request('GET', '/api/forms/')
    
    def update_form(self, form_id: str, config: Dict) -> Dict:
        """
        Update form configuration
        
        Args:
            form_id: The form ID
            config: Updated configuration
        
        Returns:
            Updated form configuration
        """
        return self._request('PUT', f'/api/forms/{form_id}/', json=config)
    
    def delete_form(self, form_id: str) -> None:
        """
        Delete a form
        
        Args:
            form_id: The form ID
        """
        self._request('DELETE', f'/api/forms/{form_id}/')
    
    def generate_session_link(
        self,
        form_id: str,
        session_data: Optional[Dict] = None,
        expires_in_hours: int = 24
    ) -> Dict:
        """
        Generate a session-specific magic link
        
        Args:
            form_id: The form ID
            session_data: Custom data to attach to the session
            expires_in_hours: Hours until link expires (default: 24)
        
        Returns:
            Dict with session_id, magic_link, expires_at
        """
        payload = {
            'session_data': session_data or {},
            'expires_in_hours': expires_in_hours
        }
        return self._request('POST', f'/api/forms/{form_id}/generate-link/', json=payload)
    
    def get_session(self, session_id: str) -> Dict:
        """
        Get session details
        
        Args:
            session_id: The session ID
        
        Returns:
            Session details dictionary
        """
        return self._request('GET', f'/api/sessions/{session_id}/')
    
    def list_sessions(self, form_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
        """
        List sessions
        
        Args:
            form_id: Filter by form ID (optional)
            status: Filter by status (optional)
        
        Returns:
            List of sessions
        """
        params = {}
        if status:
            params['status'] = status
        
        if form_id:
            endpoint = f'/api/forms/{form_id}/sessions/'
        else:
            endpoint = '/api/sessions/'
        
        return self._request('GET', endpoint, params=params)
    
    def retry_webhook(self, session_id: str) -> Dict:
        """
        Retry webhook delivery for a completed session
        
        Args:
            session_id: The session ID
        
        Returns:
            Response dictionary
        """
        return self._request('POST', f'/api/sessions/{session_id}/retry-webhook/')
    
    @staticmethod
    def verify_webhook(payload: Dict, signature: str, webhook_secret: str) -> bool:
        """
        Verify webhook signature
        
        Args:
            payload: The webhook payload
            signature: The signature from X-VoiceForm-Signature header
            webhook_secret: Your webhook secret
        
        Returns:
            True if signature is valid
        """
        import hmac
        import hashlib
        
        payload_str = json.dumps(payload, sort_keys=True)
        expected_signature = hmac.new(
            webhook_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={expected_signature}" == signature


# Helper functions for building form configurations

def create_text_field(
    name: str,
    prompt: str,
    required: bool = True,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
) -> Dict:
    """Create a text field definition"""
    field = {
        'name': name,
        'type': 'text',
        'required': required,
        'prompt': prompt
    }
    
    validation = {}
    if min_length:
        validation['min_length'] = min_length
    if max_length:
        validation['max_length'] = max_length
    
    if validation:
        field['validation'] = validation
    
    return field


def create_number_field(
    name: str,
    prompt: str,
    required: bool = True,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    integer_only: bool = False
) -> Dict:
    """Create a number field definition"""
    field = {
        'name': name,
        'type': 'number',
        'required': required,
        'prompt': prompt
    }
    
    validation = {}
    if min_value is not None:
        validation['min'] = min_value
    if max_value is not None:
        validation['max'] = max_value
    if integer_only:
        validation['integer_only'] = True
    
    if validation:
        field['validation'] = validation
    
    return field


def create_choice_field(
    name: str,
    prompt: str,
    options: List[str],
    required: bool = True
) -> Dict:
    """Create a choice field definition"""
    return {
        'name': name,
        'type': 'choice',
        'required': required,
        'prompt': prompt,
        'validation': {
            'options': options
        }
    }


def create_email_field(name: str, prompt: str, required: bool = True) -> Dict:
    """Create an email field definition"""
    return {
        'name': name,
        'type': 'email',
        'required': required,
        'prompt': prompt
    }


def create_boolean_field(name: str, prompt: str, required: bool = True) -> Dict:
    """Create a boolean field definition"""
    return {
        'name': name,
        'type': 'boolean',
        'required': required,
        'prompt': prompt
    }

