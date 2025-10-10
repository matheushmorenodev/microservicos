from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') # Lendo do .env
DEBUG = True
ALLOWED_HOSTS = []

# Apenas o essencial para Celery e Django funcionarem juntos
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'resources', # Para que o Celery encontre o tasks.py
]

ROOT_URLCONF = "servico_permissao.urls"

# Não precisamos de banco de dados, middlewares, templates, etc.
DATABASES = {}
MIDDLEWARE = []
TEMPLATES = []
# ...pode remover as outras configurações como AUTH_PASSWORD_VALIDATORS, etc.

# Configuração do Celery
CELERY_BROKER_URL = 'amqp://guest:guest@rabbitmq:5672//'
CELERY_RESULT_BACKEND = 'rpc://'
CELERY_TIMEZONE = 'America/Sao_Paulo'