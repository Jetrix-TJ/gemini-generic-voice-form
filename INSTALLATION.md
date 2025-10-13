# VoiceGen Installation Guide

Complete step-by-step installation guide for VoiceGen AI Voice Form Service.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8 or higher** - [Download Python](https://www.python.org/downloads/)
- **Redis** - Required for WebSocket support
- **Google Gemini API Key** - [Get your key](https://makersuite.google.com/app/apikey)
- **Git** (optional) - For cloning the repository

## Installation Steps

### Step 1: Get the Code

#### Option A: Clone from Git
```bash
git clone https://github.com/your-org/voicegen.git
cd voicegen
```

#### Option B: Download ZIP
Download and extract the ZIP file, then navigate to the directory.

### Step 2: Create Virtual Environment

#### On Windows:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### On macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- Django 5.0+
- Django Channels for WebSockets
- Google Generative AI SDK
- Celery for background tasks
- And all other dependencies

### Step 4: Configure Environment

1. Copy the environment template:
   ```bash
   # Windows
   copy .env.template .env
   
   # macOS/Linux
   cp .env.template .env
   ```

2. Edit `.env` file and set at minimum:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   SECRET_KEY=your_random_secret_key_here
   DEBUG=True
   REDIS_URL=redis://localhost:6379/0
   ```

3. Generate a secret key:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

### Step 5: Install Redis

#### Windows:
1. **Option A - Via Chocolatey:**
   ```powershell
   choco install redis-64
   redis-server
   ```

2. **Option B - Via WSL:**
   ```bash
   wsl --install
   # Then in WSL:
   sudo apt-get install redis-server
   redis-server
   ```

3. **Option C - Docker:**
   ```powershell
   docker run -d -p 6379:6379 --name redis redis:alpine
   ```

#### macOS:
```bash
brew install redis
brew services start redis

# Verify
redis-cli ping
# Should return: PONG
```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Verify
redis-cli ping
# Should return: PONG
```

### Step 6: Initialize Database

```bash
python manage.py migrate
```

This creates all necessary database tables.

### Step 7: Create API Key

```bash
python manage.py create_api_key "My First API Key"
```

**SAVE THE API KEY** - You'll need it for all API requests!

Alternatively, create one via Django shell:
```bash
python manage.py shell
```
```python
from voice_flow.models import APIKey
api_key = APIKey.objects.create(name="My API Key")
print(f"Your API Key: {api_key.key}")
exit()
```

### Step 8: Test Gemini Connection

```bash
python examples/test_gemini_connection.py
```

This verifies your Gemini API key is working correctly.

### Step 9: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Step 10: Start the Server

#### Development Server (with WebSocket support):
```bash
daphne voicegen.asgi:application --bind 0.0.0.0 --port 8000
```

#### Or use Docker Compose (recommended for production):
```bash
docker-compose up --build
```

### Step 11: Verify Installation

Open your browser and visit:
- http://localhost:8000/ - Home page
- http://localhost:8000/health/ - Health check (should return `{"status": "healthy"}`)

## Post-Installation

### Create a Superuser (Optional)

For Django admin access:
```bash
python manage.py createsuperuser
```

Then visit: http://localhost:8000/admin/

### Start Background Worker (Optional)

For webhook delivery and background tasks:
```bash
# In a new terminal with venv activated:
celery -A voicegen worker -l info
```

### Test Webhook Receiver

For local testing of webhooks:
```bash
cd examples
pip install -r requirements.txt
python webhook_receiver.py
```

This starts a local webhook server at http://localhost:5000

## Quick Test

Create a test form:
```bash
python examples/create_sample_form.py YOUR_API_KEY
```

This will:
1. Create a sample customer feedback form
2. Generate a session link
3. Print the magic link to visit

## Troubleshooting

### Issue: ModuleNotFoundError

**Solution:** Make sure virtual environment is activated and dependencies are installed:
```bash
# Activate venv
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\Activate.ps1  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Issue: Redis Connection Refused

**Solution:** Make sure Redis is running:
```bash
redis-cli ping
# Should return: PONG

# If not running:
redis-server  # Start manually
# or
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

### Issue: WebSocket Connection Failed

**Solution:** Use `daphne` instead of Django's `runserver`:
```bash
daphne voicegen.asgi:application --port 8000
```

### Issue: "Table does not exist"

**Solution:** Run migrations:
```bash
python manage.py migrate
```

### Issue: Static files not loading

**Solution:** Collect static files:
```bash
python manage.py collectstatic --noinput
```

### Issue: GEMINI_API_KEY not configured

**Solution:**
1. Get API key from https://makersuite.google.com/app/apikey
2. Add to `.env` file:
   ```env
   GEMINI_API_KEY=your_actual_key_here
   ```
3. Restart the server

## Docker Installation (Alternative)

If you prefer Docker:

1. **Install Docker and Docker Compose**

2. **Create .env file:**
   ```bash
   cp .env.template .env
   # Edit .env with your Gemini API key
   ```

3. **Start services:**
   ```bash
   docker-compose up --build
   ```

4. **Create API key:**
   ```bash
   docker-compose exec web python manage.py create_api_key "Docker API Key"
   ```

5. **Visit:** http://localhost:8000

## Verification Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with Gemini API key
- [ ] Redis running (`redis-cli ping` returns PONG)
- [ ] Database migrated (`python manage.py migrate`)
- [ ] API key created
- [ ] Server starts without errors
- [ ] Health check works (http://localhost:8000/health/)
- [ ] Can access home page (http://localhost:8000/)

## Next Steps

1. Read [QUICK_START.md](QUICK_START.md) for usage examples
2. Explore the [README.md](README.md) for API documentation
3. Check [examples/](examples/) for code samples
4. Review [sdk/python/](sdk/python/) for SDK usage

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review [GitHub Issues](https://github.com/your-org/voicegen/issues)
3. Join our [Discord community](https://discord.gg/voicegen)
4. Email support@voicegen.ai

## Production Deployment

For production deployment, see [DEPLOYMENT.md](docs/DEPLOYMENT.md) which covers:
- PostgreSQL setup
- HTTPS/WSS configuration
- Environment security
- Scaling considerations
- Monitoring and logging

---

🎉 **Congratulations!** You've successfully installed VoiceGen!

