# 🗣️ VoiceGen - AI Voice Form Service

Transform data collection with natural voice conversations powered by Google Gemini AI. VoiceGen allows you to create interactive voice forms that users can complete naturally through conversation, with all data automatically structured and delivered to your systems via webhooks.

## 🌟 Features

### Core Platform

- **🗣️ Natural Voice Conversations**: AI-powered voice interactions using Google Gemini 2.0 Flash (latest with native audio)
- **⚡ Real-time Processing**: WebSocket-based live audio streaming and processing
- **🔗 Magic Link Generation**: Create unique, shareable form sessions with expiration
- **📡 Webhook Callbacks**: Receive structured data at your specified endpoints
- **🎯 Zero Storage**: No data persistence - everything flows through to your systems
- **📱 Mobile Optimized**: Responsive design works on all devices

### Developer Experience

- **🚀 RESTful API**: Clean, intuitive API for form creation and management
- **📚 SDK Support**: Python SDK with more languages coming soon
- **🔐 Secure Authentication**: API key-based authentication with webhook verification
- **📊 Session Analytics**: Track completion rates, duration, and success metrics
- **🛠️ Easy Integration**: Drop-in solution for any application stack

### Advanced Capabilities

- **🎨 Configurable AI Prompts**: Customize conversation style and personality
- **✅ Dynamic Validation**: Real-time field validation with custom rules
- **🌍 Multi-language Support**: Support for multiple languages and dialects
- **♿ Accessibility**: Screen reader compatible with WCAG 2.1 compliance
- **🔄 Session Recovery**: Robust error handling with connection recovery

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/your-org/voicegen.git
cd voicegen
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Create `.env` file in the project root:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_django_secret_key
DEBUG=True

# Database (Optional - defaults to SQLite)
DATABASE_URL=postgresql://user:pass@localhost:5432/voiceforms

# Redis (Required for WebSocket support)
REDIS_URL=redis://localhost:6379/0

# Security
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
```

### 3. Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser  # Optional: for admin access
```

### 4. Run the Service

```bash
# Development (WebSocket support required)
daphne voicegen.asgi:application --port 8000

# Or with Docker
docker-compose up --build
```

### 5. Create an API Key

```bash
python manage.py shell
```

```python
from voice_flow.models import APIKey
api_key = APIKey.objects.create(name="My First Key")
print(f"API Key: {api_key.key}")
```

### 6. Verify Installation

```bash
curl -X GET http://localhost:8000/health/
# Should return: {"status": "healthy", "version": "1.0.0"}
```

## 📖 API Usage

### Create a Form

```bash
curl -X POST http://localhost:8000/api/forms/ \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Customer Feedback Form",
    "description": "Collect customer feedback through voice",
    "fields": [
      {
        "name": "customer_name",
        "type": "text",
        "required": true,
        "prompt": "What'\''s your full name?"
      },
      {
        "name": "satisfaction_rating",
        "type": "number",
        "required": true,
        "prompt": "On a scale of 1-10, how satisfied are you?",
        "validation": {"min": 1, "max": 10}
      }
    ],
    "ai_prompt": "Hello! I'\''m here to collect your feedback.",
    "callback_url": "https://your-app.com/webhook/feedback",
    "success_message": "Thank you for your feedback!"
  }'
```

### Generate Session Link

```bash
curl -X POST http://localhost:8000/api/forms/{form_id}/generate-link/ \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "session_data": {"user_id": "123", "source": "email"},
    "expires_in_hours": 48
  }'
```

## 🐍 Python SDK Usage

```python
from voiceforms import VoiceFormSDK
from voiceforms.client import create_text_field, create_number_field

# Initialize SDK
sdk = VoiceFormSDK(api_key='your_api_key')

# Create a form
form = sdk.create_form({
    'name': 'Lead Qualification',
    'fields': [
        create_text_field('company_name', 'What company do you work for?'),
        create_number_field('budget', 'What is your budget?', min_value=0)
    ],
    'ai_prompt': 'Hi! Let me help you get started.',
    'callback_url': 'https://mycrm.com/webhook/leads'
})

# Generate a session link
session = sdk.generate_session_link(
    form_id=form['form_id'],
    session_data={'lead_source': 'website'},
    expires_in_hours=48
)

print(f"Magic link: {session['magic_link']}")
```

## 📡 Webhook Integration

When a form is completed, data is sent to your `callback_url`:

### Webhook Headers

```
Content-Type: application/json
X-VoiceForm-Signature: sha256=computed_signature
X-VoiceForm-Session-ID: s_xyz789abc123
User-Agent: VoiceForms-Webhook/1.0
```

### Webhook Payload

```json
{
  "form_id": "f_abc123xyz789",
  "session_id": "s_xyz789abc123",
  "completed_at": "2024-10-13T10:15:30Z",
  "data": {
    "customer_name": "John Smith",
    "satisfaction_rating": 8
  },
  "metadata": {
    "duration_seconds": 180,
    "completion_percentage": 100,
    "fields_completed": 2,
    "total_fields": 2
  }
}
```

### Verify Webhook Signature

```python
import hmac
import hashlib
import json

def verify_webhook(payload, signature, webhook_secret):
    expected_signature = hmac.new(
        webhook_secret.encode(),
        json.dumps(payload, sort_keys=True).encode(),
        hashlib.sha256
    ).hexdigest()
    
    return f"sha256={expected_signature}" == signature
```

## 🏗️ Architecture

### Technology Stack

**Backend:**
- Django 5.0+ - Web framework and API
- Django Channels - WebSocket support
- Google Gemini 2.0 Flash - AI voice processing with native audio
- PostgreSQL/SQLite - Database
- Redis - Channel layer and caching
- Celery - Background tasks

**Frontend:**
- Vanilla JavaScript - No framework dependencies
- Web Audio API - Real-time audio capture
- WebSocket API - Bidirectional communication
- Tailwind CSS - Responsive UI

## 📋 Field Types

| Type | Description | Validation Options |
|------|-------------|-------------------|
| `text` | Free text input | min_length, max_length, pattern |
| `number` | Numeric values | min, max, integer_only |
| `email` | Email addresses | domain_whitelist |
| `phone` | Phone numbers | country_code, format |
| `date` | Date values | min_date, max_date |
| `boolean` | Yes/No questions | - |
| `choice` | Single selection | options (required) |
| `multi_choice` | Multiple selections | options, min_choices, max_choices |

## 🔧 Development

### Running Tests

```bash
python manage.py test
```

### Code Structure

```
voicegen/
├── voicegen/              # Django project root
│   ├── settings.py        # Main configuration
│   ├── urls.py            # URL routing
│   └── asgi.py            # ASGI configuration
├── voice_flow/            # Core application
│   ├── models.py          # Data models
│   ├── views.py           # API views
│   ├── consumers.py       # WebSocket consumers
│   ├── ai_service.py      # AI integration
│   ├── tasks.py           # Background tasks
│   └── serializers.py     # API serializers
├── sdk/python/            # Python SDK
├── templates/             # HTML templates
├── static/                # Static assets
└── docker-compose.yml     # Docker setup
```

## 🐳 Docker Deployment

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `SECRET_KEY` | Yes | - | Django secret key |
| `DEBUG` | No | False | Debug mode |
| `ALLOWED_HOSTS` | No | localhost | Allowed hosts |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection |
| `REDIS_URL` | No | redis://localhost:6379/0 | Redis connection |
| `WEBHOOK_TIMEOUT` | No | 30 | Webhook timeout (seconds) |

## 📚 Documentation

- [API Documentation](docs/API.md)
- [SDK Examples](docs/SDK_EXAMPLES.md)
- [Webhook Guide](docs/WEBHOOKS.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📧 Email: support@voicegen.ai
- 💬 Discord: [Join our community](https://discord.gg/voicegen)
- 📖 Documentation: [docs.voicegen.ai](https://docs.voicegen.ai)
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/voicegen/issues)

## 🙏 Acknowledgments

- Powered by Google Gemini AI
- Built with Django and Django Channels
- UI styled with Tailwind CSS

---

Made with ❤️ by the VoiceGen Team

