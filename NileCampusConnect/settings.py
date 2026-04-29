# NileCampusConnect/settings.py

from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# ── Load .env for local development ─────────────────────────────────────────
# On Render, variables are injected directly into the environment by the
# dashboard — no .env file is present there, so load_dotenv() is a no-op.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ─────────────────────────────────────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────────────────────────────────────
# Generate a key:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-fallback-only-for-local-dev'
)

# Default False — must be explicitly set to True in local .env
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Accepts a comma-separated list: "myapp.onrender.com,localhost"
_raw_hosts = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()] or ['localhost', '127.0.0.1']

# Required in Django 4.0+ when running behind Render's HTTPS proxy
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}"
    for host in ALLOWED_HOSTS
    if host not in ('localhost', '127.0.0.1', '*')
]

# ─────────────────────────────────────────────────────────────────────────────
# APPLICATION DEFINITION
# ─────────────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'core',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise must be immediately after SecurityMiddleware and
    # before everything else — it short-circuits static file requests
    # before they hit the Django view layer.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'NileCampusConnect.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'NileCampusConnect.wsgi.application'

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# dj-database-url reads DATABASE_URL from the environment.
# Render injects this automatically when you attach a PostgreSQL instance.
# Falls back to local SQLite when DATABASE_URL is not set.
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,        # keep DB connections alive for 10 min (Render best practice)
        conn_health_checks=True, # recycle stale connections after dyno sleep
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─────────────────────────────────────────────────────────────────────────────
# INTERNATIONALISATION
# ─────────────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────────────────────
# STATIC FILES
# collectstatic gathers everything into STATIC_ROOT.
# WhiteNoise serves it from there in production — no separate CDN needed.
#
# Note: no STATICFILES_DIRS entry is needed because all your static files
# live inside core/static/, which collectstatic finds automatically.
# Adding a non-existent path here would crash the build.
# ─────────────────────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise compression + long-lived cache headers (hashed filenames)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ─────────────────────────────────────────────────────────────────────────────
# MEDIA FILES
# Render's filesystem is ephemeral — uploaded files are lost on redeploy.
# For a production app, swap MEDIA storage for Cloudinary or AWS S3.
# This is fine for a demo/defense.
# ─────────────────────────────────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'core.CustomUser'

AUTHENTICATION_BACKENDS = [
    'core.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────────────────────────────────────
# PAYSTACK (set in Render environment variables, never commit the real key)
# ─────────────────────────────────────────────────────────────────────────────
PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', '')