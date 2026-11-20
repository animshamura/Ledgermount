import os
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "prod-hardened-fallback-key")
DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'rest_framework.authtoken',
    'rest_framework',
    'drf_spectacular',
    'django_prometheus',
    'src.domains.ledger.apps.LedgerConfig',
    'src.domains.webhooks.apps.WebhooksConfig',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'src.api.middleware.idempotency.RedisIdempotencyMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DATABASE_ROUTERS = ['config.db_routers.cqrs_router.PrimaryReplicaRouter']

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    parsed_database = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed_database.path.lstrip('/'),
            'USER': parsed_database.username,
            'PASSWORD': parsed_database.password,
            'HOST': parsed_database.hostname,
            'PORT': parsed_database.port or 5432,
            'OPTIONS': {'sslmode': os.getenv('DB_SSLMODE', 'require')},
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv("DB_NAME", "ledger_prod"),
            'USER': os.getenv("DB_USER", "postgres"),
            'PASSWORD': os.getenv("DB_PASSWORD", "postgres"),
            'HOST': os.getenv("DB_HOST", "postgres-primary"),
            'PORT': os.getenv("DB_PORT", "5432"),
        }
    }

REDIS_URL = os.getenv("REDIS_URL", "").strip()
parsed_redis = urlparse(REDIS_URL) if REDIS_URL else None
internal_redis_hosts = {"redis", "localhost", "127.0.0.1", "host"}
use_external_redis = bool(
    parsed_redis
    and parsed_redis.scheme in {"redis", "rediss"}
    and parsed_redis.hostname
    and parsed_redis.hostname not in internal_redis_hosts
)

CACHES = (
    {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    if use_external_redis
    else {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ledger-vercel-cache',
        }
    }
)

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAdminUser'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_RATES': {'staff_login': '5/minute'},
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Industrial Ledger Backend API',
    'DESCRIPTION': 'API schema for ledger transfers and webhook event flow.',
    'VERSION': '1.0.0',
}

TIME_ZONE = 'UTC'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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
