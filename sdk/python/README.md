# VoiceForms Python SDK

Official Python SDK for the VoiceForms AI Voice Form Service.

## Installation

```bash
pip install voiceforms-python
```

Or install from source:

```bash
cd sdk/python
pip install -e .
```

## Quick Start

```python
from voiceforms import VoiceFormSDK
from voiceforms.client import create_text_field, create_choice_field

# Initialize SDK
sdk = VoiceFormSDK(
    api_key='your_api_key',
    base_url='http://localhost:8000'  # or your hosted instance
)

# Create a form
form_config = {
    'name': 'Customer Feedback Form',
    'description': 'Collect customer feedback',
    'fields': [
        create_text_field('name', 'What is your name?', required=True),
        create_choice_field(
            'satisfaction',
            'How satisfied are you with our service?',
            options=['Very Satisfied', 'Satisfied', 'Neutral', 'Unsatisfied'],
            required=True
        )
    ],
    'ai_prompt': 'Hello! I\'d love to get your feedback. This will just take a minute.',
    'callback_url': 'https://your-app.com/webhook/feedback'
}

# Create the form
result = sdk.create_form(form_config)
print(f"Form created: {result['form_id']}")
print(f"Magic link: {result['magic_link']}")

# Generate a session link
session = sdk.generate_session_link(
    form_id=result['form_id'],
    session_data={'user_id': '12345', 'source': 'email'},
    expires_in_hours=48
)

print(f"Session link: {session['magic_link']}")
```

## Webhook Verification

```python
from flask import Flask, request
from voiceforms import VoiceFormSDK

app = Flask(__name__)

@app.route('/webhook/feedback', methods=['POST'])
def handle_webhook():
    payload = request.json
    signature = request.headers.get('X-VoiceForm-Signature')
    webhook_secret = 'your_webhook_secret'
    
    # Verify signature
    if not VoiceFormSDK.verify_webhook(payload, signature, webhook_secret):
        return 'Invalid signature', 403
    
    # Process the data
    form_id = payload['form_id']
    session_id = payload['session_id']
    data = payload['data']
    
    print(f"Received data: {data}")
    
    return 'OK', 200
```

## API Reference

### VoiceFormSDK

#### Constructor
```python
sdk = VoiceFormSDK(api_key: str, base_url: str = 'http://localhost:8000')
```

#### Methods

- `create_form(config: Dict) -> Dict` - Create a new form
- `get_form(form_id: str) -> Dict` - Get form by ID
- `list_forms() -> List[Dict]` - List all forms
- `update_form(form_id: str, config: Dict) -> Dict` - Update form
- `delete_form(form_id: str) -> None` - Delete form
- `generate_session_link(form_id: str, session_data: Dict = {}, expires_in_hours: int = 24) -> Dict` - Generate session link
- `get_session(session_id: str) -> Dict` - Get session details
- `list_sessions(form_id: str = None, status: str = None) -> List[Dict]` - List sessions
- `retry_webhook(session_id: str) -> Dict` - Retry webhook delivery
- `verify_webhook(payload: Dict, signature: str, webhook_secret: str) -> bool` (static) - Verify webhook signature

### Helper Functions

- `create_text_field(name, prompt, required=True, min_length=None, max_length=None)`
- `create_number_field(name, prompt, required=True, min_value=None, max_value=None, integer_only=False)`
- `create_choice_field(name, prompt, options, required=True)`
- `create_email_field(name, prompt, required=True)`
- `create_boolean_field(name, prompt, required=True)`

## License

MIT License

