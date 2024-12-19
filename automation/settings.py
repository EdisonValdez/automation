import os
from pathlib import Path
import dj_database_url
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

load_dotenv(dotenv_path='./.env')

BASE_DIR = Path(__file__).resolve().parent.parent
 
# Environment Variables
# DEBUG = os.getenv('DEBUG', 'False').lower() == 'false' - With this one the deployment failed!
# DEBUG = os.getenv('DEBUG', 'True').lower() == 'true' - NO It is showing the debug page
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'


DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', 'True').lower(
) == 'true'  # original in pro set true
 
# DEBUG = True if DEVELOPMENT_MODE else False

if DEVELOPMENT_MODE:
    BASE_URL = 'http://localhost:8000'
else:
    BASE_URL = 'https://orca-app-jasq8.ondigitalocean.app'

# Set to 'True' in production when using S3
USE_S3 = os.getenv('USE_S3', 'False').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', get_random_secret_key())
ALLOWED_HOSTS = ["*"]

# Installed Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'automation',
    'django_celery_results',
    'django.contrib.postgres',
    'storages',
]

CSRF_TRUSTED_ORIGINS = ["https://localsecrets.zoondia.org"]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'automation.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'automation.wsgi.application'


# Configuración de la base de datos
if DEVELOPMENT_MODE:
    DATABASES = {
        'default': {

            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'automation-18102024'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'Thesecret1'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.parse(
            os.getenv('DATABASE_URL'),
            conn_max_age=600, ssl_require=True)}

# Static and Media file settings
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Media Files Configuration
if USE_S3:
    # DigitalOcean Spaces (S3) settings for production
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = os.getenv(
        'AWS_S3_ENDPOINT_URL', 'https://nyc3.digitaloceanspaces.com')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'nyc3')
    AWS_S3_SIGNATURE_VERSION = 's3v4'

    # Correctly handle S3 custom domain
    AWS_S3_CUSTOM_DOMAIN = os.getenv(
        'AWS_S3_CUSTOM_DOMAIN',
        f"{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_ENDPOINT_URL.replace('https://', '')}")

    AWS_DEFAULT_ACL = 'public-read'
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}

    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
else:
    # Local file storage for development
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Static Files Storage
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

DEFAULT_IMAGE_URL = os.getenv(
    'DEFAULT_IMAGE_URL',
    'https://www.localsecrets.travel/wp-content/uploads/2024/08/cropped-cropped-logo-web-1.png'
)

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Authentication Configuration
AUTH_USER_MODEL = 'automation.CustomUser'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'automation': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        } 
    },
}

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.mailersend.net')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_HOST_USER = os.getenv(
    'EMAIL_HOST_USER', 'communications@localsecrets.travel')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'Lex7Mi70bZkyhuUU')
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL', 'communications@localsecrets.travel')
TOKEN = "mlsn.8180f5205222863e3187181245657328c6b7c29b64bb398549fb8725e2112aed"
# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5 MB
FILE_UPLOAD_PERMISSIONS = 0o644
REQUEST_TIMEOUT = 120  # in seconds

# Database Options
DATABASE_OPTIONS = {
    'connect_timeout': 60,
}

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all origins in development
if not DEBUG:
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# Static Files Finders
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# Message Storage
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'


# Ensure SECURITY settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# API keys and additional configs
TRANSLATION_OPENAI_API_KEY = os.getenv('GENAI_OPENAI_API_KEY')
GENAI_OPENAI_API_KEY = os.getenv('GENAI_OPENAI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SERPAPI_KEY = os.getenv('SERPAPI_KEY')

DEFAULT_IMAGES = 3

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME')
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL')
 
LOCAL_SECRET_BASE_URL = os.environ.get('LOCAL_SECRET_BASE_URL')
SIGATURE_SECRET = os.environ.get('SIGATURE_SECRET')
