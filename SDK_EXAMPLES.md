# Voice Flow SDK - Usage Examples

## Quick Start

### 1. Create a Form (Pre-built Template)

```bash
curl -X POST http://localhost:8000/api/sdk/forms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Patient Intake Form",
    "description": "Medical patient intake form",
    "use_prebuilt": true,
    "prebuilt_type": "patient_intake",
    "callback_url": "https://your-domain.com/webhook/patient",
    "callback_secret": "your-webhook-secret",
    "ai_instructions": "You are a medical assistant collecting patient information. Be professional and empathetic."
  }'
```

**Response:**
```json
{
  "success": true,
  "form_id": "123e4567-e89b-12d3-a456-426614174000",
  "form_name": "Patient Intake Form",
  "magic_link_url": "/voice/magic/123e4567-e89b-12d3-a456-426614174000/",
  "webhook_url": "/api/webhook/123e4567-e89b-12d3-a456-426614174000/",
  "message": "Form created successfully"
}
```

### 2. Generate Magic Link

```bash
curl -X POST http://localhost:8000/api/sdk/magic-link/ \
  -H "Content-Type: application/json" \
  -d '{
    "form_id": "123e4567-e89b-12d3-a456-426614174000",
    "expiry_hours": 24,
    "custom_data": {
      "patient_id": "P12345",
      "appointment_time": "2024-01-15T10:00:00Z"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "magic_link": "http://localhost:8000/voice/magic/abc123def456/",
  "expires_in_hours": 24,
  "message": "Magic link generated successfully"
}
```

### 3. Set Up Webhook Endpoint

Create a webhook endpoint in your application to receive form data:

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import hmac
import hashlib

@csrf_exempt
def webhook_handler(request):
    if request.method == 'POST':
        # Verify webhook signature (optional but recommended)
        signature = request.headers.get('X-Signature')
        if signature and not verify_signature(request.body, signature, 'your-webhook-secret'):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
        
        # Parse form data
        data = json.loads(request.body)
        
        # Extract form data
        form_data = data.get('form_data', {})
        session_id = data.get('session_id')
        form_name = data.get('form_name')
        
        # Process the form data
        print(f"Received form data for {form_name}: {form_data}")
        
        # Save to your database, send emails, etc.
        # ...
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def verify_signature(payload, signature, secret):
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={expected_signature}"
    return hmac.compare_digest(signature, expected_signature)
```

## Advanced Examples

### Custom Form Creation

```bash
curl -X POST http://localhost:8000/api/sdk/forms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Job Application Form",
    "description": "Employment application form",
    "sections": [
      {
        "title": "Personal Information",
        "description": "Basic candidate details",
        "fields": [
          {
            "name": "full_name",
            "label": "Full Name",
            "type": "text",
            "required": true,
            "validation": {
              "min_length": 2,
              "max_length": 100
            }
          },
          {
            "name": "email",
            "label": "Email Address",
            "type": "email",
            "required": true
          },
          {
            "name": "phone",
            "label": "Phone Number",
            "type": "phone",
            "required": true
          }
        ]
      },
      {
        "title": "Professional Information",
        "description": "Work experience and qualifications",
        "fields": [
          {
            "name": "current_position",
            "label": "Current Position",
            "type": "text"
          },
          {
            "name": "years_experience",
            "label": "Years of Experience",
            "type": "number"
          },
          {
            "name": "education",
            "label": "Education",
            "type": "textarea",
            "placeholder": "List your educational background"
          },
          {
            "name": "resume",
            "label": "Resume/CV",
            "type": "file",
            "allowed_types": ["application/pdf", "application/msword"],
            "max_size": 5242880
          }
        ]
      }
    ],
    "callback_url": "https://your-domain.com/webhook/job-application",
    "callback_secret": "your-webhook-secret",
    "ai_instructions": "You are an HR assistant collecting job application information. Be professional and helpful."
  }'
```

### Retrieve Form Data

```bash
curl -X GET http://localhost:8000/api/sdk/form-data/{session_id}/
```

**Response:**
```json
{
  "success": true,
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "magic_link_id": "abc123def456",
  "form_name": "Patient Intake Form",
  "completion_status": "completed",
  "created_at": "2024-01-15T09:00:00Z",
  "completed_at": "2024-01-15T09:15:00Z",
  "form_data": {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-01",
    "phone": "+1234567890",
    "email": "john.doe@example.com",
    "current_symptoms": "Headache and fever",
    "medications": "Aspirin 100mg daily",
    "allergies": "Penicillin"
  },
  "submissions": [
    {
      "id": "456e7890-e89b-12d3-a456-426614174000",
      "timestamp": "2024-01-15T09:15:00Z",
      "callback_delivered": true,
      "callback_attempts": 1
    }
  ]
}
```

### List All Forms

```bash
curl -X GET http://localhost:8000/api/sdk/forms/
```

**Response:**
```json
{
  "success": true,
  "forms": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Patient Intake Form",
      "description": "Medical patient intake form",
      "created_at": "2024-01-15T08:00:00Z",
      "magic_link_url": "/voice/magic/123e4567-e89b-12d3-a456-426614174000/",
      "webhook_url": "/api/webhook/123e4567-e89b-12d3-a456-426614174000/",
      "callback_configured": true
    }
  ],
  "count": 1
}
```

## Webhook Payload Structure

When a form is submitted, your webhook will receive a POST request with the following structure:

```json
{
  "form_id": "123e4567-e89b-12d3-a456-426614174000",
  "form_name": "Patient Intake Form",
  "session_id": "456e7890-e89b-12d3-a456-426614174000",
  "magic_link_id": "abc123def456",
  "submission_timestamp": "2024-01-15T09:15:00Z",
  "form_data": {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1990-01-01",
    "phone": "+1234567890",
    "email": "john.doe@example.com",
    "current_symptoms": "Headache and fever",
    "medications": "Aspirin 100mg daily",
    "allergies": "Penicillin"
  },
  "completion_status": "completed"
}
```

## Integration Examples

### Python/Django Integration

```python
import requests
import json

class VoiceFlowClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def create_form(self, form_config):
        """Create a new form"""
        response = requests.post(
            f"{self.base_url}/api/sdk/forms/",
            json=form_config
        )
        return response.json()
    
    def generate_magic_link(self, form_id, expiry_hours=24, custom_data=None):
        """Generate magic link for form"""
        response = requests.post(
            f"{self.base_url}/api/sdk/magic-link/",
            json={
                "form_id": form_id,
                "expiry_hours": expiry_hours,
                "custom_data": custom_data or {}
            }
        )
        return response.json()
    
    def get_form_data(self, session_id):
        """Retrieve form data"""
        response = requests.get(
            f"{self.base_url}/api/sdk/form-data/{session_id}/"
        )
        return response.json()

# Usage
client = VoiceFlowClient()

# Create a form
form_result = client.create_form({
    "name": "Contact Form",
    "description": "Simple contact form",
    "use_prebuilt": True,
    "prebuilt_type": "contact_form",
    "callback_url": "https://your-domain.com/webhook/contact"
})

form_id = form_result['form_id']

# Generate magic link
magic_link_result = client.generate_magic_link(form_id, 24)
magic_link = magic_link_result['magic_link']

print(f"Send this link to your users: {magic_link}")
```

### Node.js Integration

```javascript
const axios = require('axios');

class VoiceFlowClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async createForm(formConfig) {
        const response = await axios.post(`${this.baseUrl}/api/sdk/forms/`, formConfig);
        return response.data;
    }
    
    async generateMagicLink(formId, expiryHours = 24, customData = {}) {
        const response = await axios.post(`${this.baseUrl}/api/sdk/magic-link/`, {
            form_id: formId,
            expiry_hours: expiryHours,
            custom_data: customData
        });
        return response.data;
    }
    
    async getFormData(sessionId) {
        const response = await axios.get(`${this.baseUrl}/api/sdk/form-data/${sessionId}/`);
        return response.data;
    }
}

// Usage
const client = new VoiceFlowClient();

async function createContactForm() {
    const formResult = await client.createForm({
        name: 'Contact Form',
        description: 'Simple contact form',
        use_prebuilt: true,
        prebuilt_type: 'contact_form',
        callback_url: 'https://your-domain.com/webhook/contact'
    });
    
    const magicLinkResult = await client.generateMagicLink(formResult.form_id, 24);
    console.log(`Magic link: ${magicLinkResult.magic_link}`);
}

createContactForm();
```

## Pre-built Form Types

### 1. Patient Intake Form
- Personal information (name, DOB, contact)
- Medical information (symptoms, medications, allergies)
- Insurance information
- Emergency contacts

### 2. Contact Form
- Name, email, phone
- Message/description
- Simple and quick

### 3. Job Application Form
- Personal information
- Professional experience
- Education background
- File upload for resume/CV

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error description"
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad request (validation errors)
- `401`: Unauthorized (invalid webhook signature)
- `404`: Not found (form/session not found)
- `500`: Internal server error

## Security Best Practices

1. **Webhook Signatures**: Always verify webhook signatures using the provided secret
2. **HTTPS**: Use HTTPS in production for all webhook URLs
3. **Input Validation**: Validate all form data on your end
4. **Rate Limiting**: Implement rate limiting on your webhook endpoints
5. **Error Handling**: Implement proper error handling and retry logic

## Testing

Use the test webhook endpoint for development:

```bash
curl -X POST http://localhost:8000/api/sdk/test-webhook/ \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

This will echo back your request for testing purposes.
