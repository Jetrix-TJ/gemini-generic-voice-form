#!/bin/bash
# VoiceGen Setup Script

echo "========================================"
echo "🗣️  VoiceGen Setup Script"
echo "========================================"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    if [ -f .env.template ]; then
        cp .env.template .env
        echo "✓ Created .env file. Please edit it with your configuration."
    else
        echo "❌ .env.template not found!"
    fi
else
    echo "✓ .env file exists"
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs
mkdir -p staticfiles
mkdir -p static/voice_flow/js
echo "✓ Directories created"

# Run migrations
echo ""
echo "Running database migrations..."
python manage.py migrate
echo "✓ Migrations complete"

# Collect static files
echo ""
echo "Collecting static files..."
python manage.py collectstatic --noinput
echo "✓ Static files collected"

# Check Redis connection
echo ""
echo "Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping > /dev/null 2>&1; then
        echo "✓ Redis is running"
    else
        echo "⚠️  Redis is not running. Start it with:"
        echo "   - macOS: brew services start redis"
        echo "   - Linux: sudo systemctl start redis"
        echo "   - Docker: docker run -d -p 6379:6379 redis:alpine"
    fi
else
    echo "⚠️  redis-cli not found. Please install Redis."
fi

# Check Gemini API key
echo ""
echo "Checking configuration..."
source .env
if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "⚠️  GEMINI_API_KEY not configured in .env"
    echo "   Get your key from: https://makersuite.google.com/app/apikey"
else
    echo "✓ GEMINI_API_KEY is configured"
fi

# Create superuser prompt
echo ""
echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your Gemini API key"
echo "2. Start Redis (if not running)"
echo "3. Create an API key:"
echo "   python manage.py shell"
echo "   >>> from voice_flow.models import APIKey"
echo "   >>> key = APIKey.objects.create(name='My Key')"
echo "   >>> print(key.key)"
echo ""
echo "4. Start the server:"
echo "   daphne voicegen.asgi:application --port 8000"
echo ""
echo "5. Visit http://localhost:8000"
echo ""

