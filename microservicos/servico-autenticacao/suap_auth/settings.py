# servico-autenticacao/suap_auth/settings.py
from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env
load_dotenv() 

BASE_DIR = Path(__file__).resolve().parent.parent

# Buscando Variavel de Ambiente.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'default-insecure-key-for-dev')

# ✅ Centralize URLs externas aqui para fácil manutenção.
SUAP_BASE_URL = 'https://suap.ifsuldeminas.edu.br/api'
SUAP_TOKEN_URL = f'{SUAP_BASE_URL}/token/pair'
SUAP_USER_DATA_URL = f'{SUAP_BASE_URL}/rh/meus-dados/'


DEBUG = True
ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://192.168.1.7:8000', # Seu IP atual
]

# Aplicativos essenciais apenas para API
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'suap_auth.urls'

# Configuração mínima para DRF + JWT customizado
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'core.authentication.CustomJWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Não usamos templates, banco, nem admin
TEMPLATES = []
DATABASES = {}
AUTH_PASSWORD_VALIDATORS = []

# Internacionalização (opcional)
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# Sem arquivos estáticos
STATIC_URL = None

# --- CONFIGURAÇÃO CORS PERMISSIVA ---
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Configuração de CORS (Permitir tudo em ambiente de dev)
CORS_ALLOW_ALL_ORIGINS = True