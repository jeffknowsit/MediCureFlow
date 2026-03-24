from .base import *

# Development settings
DEBUG = True

SECRET_KEY = env('SECRET_KEY', default='django-insecure-dev-key-MediCureFlow-1234567890')

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '127.0.0.1:8000', 'localhost:8000']

# Database configuration
# Using SQLite for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Override LOCAL_APPS to exclude missing health_ai
LOCAL_APPS = [
    'apps.doctors',
    'apps.users',
    'apps.admin_system',
    'apps.payments',
    'apps.notifications',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Disable HTTPS requirements for local development
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# Enable SMTP email backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'jeffjosephchirayath1@gmail.com'
EMAIL_HOST_PASSWORD = 'iwiu pdan iibd vmvs'
DEFAULT_FROM_EMAIL = 'MediCure Plus <jeffjosephchirayath1@gmail.com>'
