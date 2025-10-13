# Quick Start Guide

Get VoiceGen up and running in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- Redis server (for WebSocket support)
- Google Gemini API key

## Step 1: Install Dependencies

```bash
# Clone the repository
git clone https://github.com/your-org/voicegen.git
cd voicegen

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

## Step 2: Configure Environment

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your-secret-key-here
DEBUG=True
REDIS_URL=redis://localhost:6379/0
```

Get your Gemini API key: https://makersuite.google.com/app/apikey

## Step 3: Initialize Database

```bash
python manage.py migrate
```

## Step 4: Create API Key

```bash
python manage.py shell
```

In the Python shell:

```python
from voice_flow.models import APIKey
api_key = APIKey.objects.create(name="Development Key")
print(f"Your API Key: {api_key.key}")
exit()
```

**Save this API key** - you'll need it for API calls!

## Step 5: Start Redis

### macOS (with Homebrew):
```bash
brew services start redis
```

### Linux:
```bash
sudo systemctl start redis
```

### Windows:
Download from https://redis.io/download or use Docker:
```bash
docker run -d -p 6379:6379 redis:alpine
```

## Step 6: Start the Server

```bash
daphne voicegen.asgi:application --port 8000
```

Or use the Django development server (for testing only):
```bash
python manage.py runserver
```

## Step 7: Test the Installation

Open your browser and visit:
- http://localhost:8000/ - Home page
- http://localhost:8000/health/ - Health check

## Step 8: Create Your First Form

Using the Python SDK:

```python
from voiceforms import VoiceFormSDK
from voiceforms.client import create_text_field, create_number_field

sdk = VoiceFormSDK(api_key='YOUR_API_KEY_HERE')

form = sdk.create_form({
    'name': 'Quick Survey',
    'fields': [
        create_text_field('name', 'What is your name?'),
        create_number_field(
            'rating',
            'On a scale of 1-10, how would you rate this service?',
            min_value=1,
            max_value=10
        )
    ],
    'ai_prompt': 'Hello! This is a quick 2-question survey.',
    'callback_url': 'https://webhook.site/unique-url'  # Use webhook.site for testing
})

print(f"Form ID: {form['form_id']}")
print(f"Magic Link: {form['magic_link']}")

# Generate a session
session = sdk.generate_session_link(form['form_id'])
print(f"Session Link: {session['magic_link']}")
```

Or using curl:

```bash
curl -X POST http://localhost:8000/api/forms/ \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Quick Survey",
    "fields": [
      {
        "name": "name",
        "type": "text",
        "required": true,
        "prompt": "What is your name?"
      }
    ],
    "ai_prompt": "Hello! Let'\''s get started.",
    "callback_url": "https://webhook.site/unique-url"
  }'
```

## Step 9: Test the Voice Interface

1. Copy the magic link from the response
2. Open it in your browser
3. Click the microphone button or type your responses
4. Complete the form

## Step 10: View Webhook Data

Visit https://webhook.site to see the webhook payload delivered to your test endpoint!

## Using Docker (Alternative)

If you prefer Docker:

```bash
# Create .env file with your settings
cp .env.example .env
# Edit .env with your Gemini API key

# Start all services
docker-compose up --build

# In another terminal, create an API key
docker-compose exec web python manage.py shell
# Then follow Step 4
```

## Troubleshooting

### Redis Connection Error
**Error**: `Connection refused` or `Error 111`
**Solution**: Make sure Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### WebSocket Connection Failed
**Error**: WebSocket connection fails
**Solution**: 
- Make sure you're using `daphne` instead of `runserver`
- Check that Redis is running

### Gemini API Error
**Error**: `Invalid API key`
**Solution**: 
- Verify your API key is correct
- Make sure it's set in the `.env` file
- Restart the server after updating `.env`

### Migration Error
**Error**: `Table already exists`
**Solution**:
```bash
rm db.sqlite3
python manage.py migrate
```

## Next Steps

- Read the [full documentation](README.md)
- Explore [API examples](docs/API_EXAMPLES.md)
- Check out [SDK examples](sdk/python/README.md)
- Learn about [webhook integration](docs/WEBHOOKS.md)

## Need Help?

- 📧 Email: support@voicegen.ai
- 💬 Discord: [Join our community](https://discord.gg/voicegen)
- 🐛 Issues: [GitHub Issues](https://github.com/your-org/voicegen/issues)

