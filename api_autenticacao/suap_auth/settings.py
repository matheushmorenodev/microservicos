from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-ds99d^hlyc-j8*pucryv_af616*qi+8+eyytgm3&d3xp34z+xf'  # troque por algo seguro em produção

DEBUG = True
ALLOWED_HOSTS = []

# Aplicativos essenciais apenas para API
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'rest_framework_simplejwt',
    'core',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'suap_auth.urls'

# Configuração mínima para DRF + JWT customizado
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'core.authentication.StatelessJWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=12),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Não usamos templates, banco, nem admin
TEMPLATES = []
DATABASES = {}
AUTH_PASSWORD_VALIDATORS = []

# Internacionalização (opcional)
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = False

# Sem arquivos estáticos
STATIC_URL = None
