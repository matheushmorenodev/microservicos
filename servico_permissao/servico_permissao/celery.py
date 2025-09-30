import os
from celery import Celery

# Define o módulo de settings do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'servico_permissao.settings')

# URL do RabbitMQ
broker_url = 'amqp://guest:guest@rabbitmq:5672//'
#Diga ao Celery para enviar os resultados de volta via AMQP (RabbitMQ)
result_backend = 'rpc://' 
app = Celery(
    'servico_permissao', 
    broker=broker_url, 
    backend=result_backend  # Use a nova variável aqui
)

# Usa as configurações do Django para o Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Carrega tarefas de todos os apps Django registrados
app.autodiscover_tasks()