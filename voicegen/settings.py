"""
Django settings for AI Voice Form Service project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# Load environment variables
load_dotenv()

# Proxy SSL Header Configuration
# This allows Django to detect HTTPS when behind a reverse proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'daphne',  # Must be at the top for WebSocket support
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'channels',
    'django_filters',
    
    # Local apps
    'voice_flow',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'voicegen.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'voicegen.wsgi.application'
ASGI_APPLICATION = 'voicegen.asgi.application'

# Database
if os.getenv('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.parse(os.getenv('DATABASE_URL'))
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Channel Layers - Use in-memory for Live API (no Redis needed!)
# Live API uses direct WebSocket connections, not channel layers
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# WhiteNoise configuration for serving static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Cookies and CSRF/session settings
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Lax is safe for same-site POSTs from forms/JS
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')

# CSRF trusted origins (for reverse proxies/custom domains)
_csrf_trusted = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted.split(',') if o.strip()]
else:
    # If DOMAIN_URL is set, add it as trusted origin (required on Django 4+ with scheme)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(os.getenv('DOMAIN_URL', ''))
        if parsed.scheme and parsed.netloc:
            CSRF_TRUSTED_ORIGINS = [f"{parsed.scheme}://{parsed.netloc}"]
    except Exception:
        pass

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'voice_flow.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if not DEBUG else []

# Celery Configuration
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Voice Form Service Settings
VOICE_FORM_SETTINGS = {
    'GEMINI_API_KEY': os.getenv('GEMINI_API_KEY'),
    # Gemini 2.5 Flash Native Audio with Live API (recommended for real-time voice)
    'GEMINI_AUDIO_MODEL': os.getenv('GEMINI_AUDIO_MODEL', 'gemini-2.5-flash-native-audio-preview-09-2025'),
    # Text model for structured extraction and summaries (must support generateContent)
    'GEMINI_TEXT_MODEL': os.getenv('GEMINI_TEXT_MODEL', 'gemini-2.0-flash-exp'),
    # Fallback model for text-based interactions
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'DEFAULT_SESSION_EXPIRY_HOURS': int(os.getenv('DEFAULT_SESSION_EXPIRY_HOURS', 24)),
    'MAX_SESSION_DURATION_MINUTES': int(os.getenv('MAX_SESSION_DURATION_MINUTES', 30)),
    'MAX_FORM_FIELDS': 50,
    'WEBHOOK_TIMEOUT': int(os.getenv('WEBHOOK_TIMEOUT', 30)),
    'WEBHOOK_RETRY_ATTEMPTS': int(os.getenv('WEBHOOK_RETRY_ATTEMPTS', 3)),
    'AI_RESPONSE_TIMEOUT': 30,
    'AUDIO_MAX_SIZE_MB': 10,
    'SUPPORTED_AUDIO_FORMATS': ['webm', 'wav', 'mp3', 'ogg', 'opus', 'pcm'],
    'SESSION_CLEANUP_HOURS': int(os.getenv('SESSION_CLEANUP_HOURS', 168)),
    'DOMAIN_URL': os.getenv('DOMAIN_URL', 'http://localhost:8000'),
    # Use Live API for real-time bidirectional audio streaming
    'USE_LIVE_API': os.getenv('USE_LIVE_API', 'True') == 'True',
    'NATIVE_AUDIO_PROCESSING': os.getenv('NATIVE_AUDIO_PROCESSING', 'True') == 'True',
    'RATE_LIMITING': {
        'api_calls_per_hour': 1000,
        'session_creates_per_hour': 100
    }
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'voicegen.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
    'loggers': {
        'voice_flow': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Ensure logs directory exists
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

