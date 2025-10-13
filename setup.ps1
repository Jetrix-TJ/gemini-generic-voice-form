# VoiceGen Setup Script for Windows PowerShell

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🗣️  VoiceGen Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
$pythonVersion = python --version 2>&1
Write-Host "✓ Python version: $pythonVersion" -ForegroundColor Green

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  .env file not found. Creating from template..." -ForegroundColor Yellow
    if (Test-Path .env.template) {
        Copy-Item .env.template .env
        Write-Host "✓ Created .env file. Please edit it with your configuration." -ForegroundColor Green
    } else {
        Write-Host "❌ .env.template not found!" -ForegroundColor Red
    }
} else {
    Write-Host "✓ .env file exists" -ForegroundColor Green
}

# Create virtual environment
if (-not (Test-Path venv)) {
    Write-Host ""
    Write-Host "Creating virtual environment..."
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Create necessary directories
Write-Host ""
Write-Host "Creating directories..."
New-Item -ItemType Directory -Force -Path logs | Out-Null
New-Item -ItemType Directory -Force -Path staticfiles | Out-Null
New-Item -ItemType Directory -Force -Path static\voice_flow\js | Out-Null
Write-Host "✓ Directories created" -ForegroundColor Green

# Run migrations
Write-Host ""
Write-Host "Running database migrations..."
python manage.py migrate
Write-Host "✓ Migrations complete" -ForegroundColor Green

# Collect static files
Write-Host ""
Write-Host "Collecting static files..."
python manage.py collectstatic --noinput
Write-Host "✓ Static files collected" -ForegroundColor Green

# Check Gemini API key
Write-Host ""
Write-Host "Checking configuration..."
if (Test-Path .env) {
    $envContent = Get-Content .env -Raw
    if ($envContent -notmatch 'GEMINI_API_KEY=(?!your_gemini_api_key_here)') {
        Write-Host "⚠️  GEMINI_API_KEY not configured in .env" -ForegroundColor Yellow
        Write-Host "   Get your key from: https://makersuite.google.com/app/apikey"
    } else {
        Write-Host "✓ GEMINI_API_KEY is configured" -ForegroundColor Green
    }
}

# Setup complete
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Edit .env file with your Gemini API key"
Write-Host "2. Install and start Redis:"
Write-Host "   Download from: https://redis.io/download"
Write-Host "   Or use Docker: docker run -d -p 6379:6379 redis:alpine"
Write-Host ""
Write-Host "3. Create an API key:"
Write-Host "   python manage.py shell"
Write-Host "   >>> from voice_flow.models import APIKey"
Write-Host "   >>> key = APIKey.objects.create(name='My Key')"
Write-Host "   >>> print(key.key)"
Write-Host ""
Write-Host "4. Start the server:"
Write-Host "   daphne voicegen.asgi:application --port 8000"
Write-Host ""
Write-Host "5. Visit http://localhost:8000"
Write-Host ""

