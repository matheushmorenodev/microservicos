# permission_service/celeryconfig.py
broker_url = 'amqp://guest:guest@rabbitmq:5672//'
result_backend = 'rpc://'

# Define a fila que este worker vai consumir
task_queues = {
    'permission_queue': {
        'exchange': 'default',
        'binding_key': 'permission_queue',
    }
}

# Configurações adicionais
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'America/Sao_Paulo'
enable_utc = True