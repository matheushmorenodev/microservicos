#servico-permissao/celeryconfig.py
import os

# Configurações do RabbitMQ
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")

broker_url = f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}'
result_backend = 'rpc://'

# Definição de Filas
task_queues = {
    'permission_queue': {
        'exchange': 'default',
        'binding_key': 'permission_queue',
    }
}

# Serialização
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Timezone
timezone = 'America/Sao_Paulo'
enable_utc = True