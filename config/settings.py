"""
Django settings for Legal Metrology Online Verification System project.
Generated for Smart India Hackathon - Weighing and Measuring Instruments Platform.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Fallback basic parser if python-dotenv is not yet installed
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# Security Settings
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-sih-2026-legal-metrology-verification-platform-change-in-production'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

_default_hosts = [
    'localhost',
    '127.0.0.1',
    '0.0.0.0',
    '.run.app',
    'ais-dev-3h7xolcpy4xhnm7wqatocz-913127136737.asia-southeast1.run.app',
    'ais-pre-3h7xolcpy4xhnm7wqatocz-913127136737.asia-southeast1.run.app',
    '*',
]
_env_hosts = (
    os.environ.get('ALLOWED_HOSTS', '').split(',')
    + os.environ.get('NG_ALLOWED_HOSTS', '').split(',')
)
ALLOWED_HOSTS = list(dict.fromkeys(
    [h.strip() for h in (_default_hosts + _env_hosts) if h.strip()]
))

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party Apps
    'rest_framework',

    # Core Modular Apps
    'accounts.apps.AccountsConfig',
    'instruments.apps.InstrumentsConfig',
    'verification.apps.VerificationConfig',
    'certificates.apps.CertificatesConfig',
    'notifications.apps.NotificationsConfig',
    'dashboard.apps.DashboardConfig',
]

MIDDLEWARE = [
    'config.middleware.IframeCookieMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'accounts.context_processors.metrology_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database Setup: Supports SQLite locally and PostgreSQL via DATABASE_URL
database_url = os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}')

if database_url.startswith('postgres://') or database_url.startswith('postgresql://'):
    parsed_db = urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed_db.path.lstrip('/'),
            'USER': parsed_db.username or '',
            'PASSWORD': parsed_db.password or '',
            'HOST': parsed_db.hostname or 'localhost',
            'PORT': parsed_db.port or '5432',
        }
    }
else:
    # Default SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-in'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_USE_FINDERS = True
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Media files (Verification proof, certificates, test reports)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication Redirections
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Reverse Proxy & Iframe Preview Settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'ALLOWALL'

# CSRF Trusted Origins
_default_csrf_origins = [
    'http://localhost',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:8001',
    'https://*.run.app',
    'https://ais-dev-3h7xolcpy4xhnm7wqatocz-913127136737.asia-southeast1.run.app',
    'https://ais-pre-3h7xolcpy4xhnm7wqatocz-913127136737.asia-southeast1.run.app',
    'https://*.google.com',
    'https://aistudio.google.com',
]
_env_csrf_origins = [
    orig.strip()
    for orig in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if orig.strip() and ('://' in orig)
]
for _ng_host in os.environ.get('NG_ALLOWED_HOSTS', '').split(','):
    _ng_host = _ng_host.strip()
    if _ng_host:
        _env_csrf_origins.append(f'https://{_ng_host}')

CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_default_csrf_origins + _env_csrf_origins))

# REST Framework settings (used for future API extensions)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
