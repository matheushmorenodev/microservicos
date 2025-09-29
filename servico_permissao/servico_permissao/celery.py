import os
from celery import Celery

# Define o módulo de settings do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'servico_permissao.settings')

# URL do RabbitMQ
broker_url = 'amqp://guest:guest@rabbitmq:5672//'

app = Celery('servico_permissao', broker=broker_url, backend='redis://redis:6379/0')

# Usa as configurações do Django para o Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega tarefas de todos os apps Django registrados
app.autodiscover_tasks()