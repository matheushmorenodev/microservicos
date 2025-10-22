# celeryconfig.py

# URL de conexão com o RabbitMQ.
broker_url = 'amqp://guest:guest@rabbitmq:5672//'

# Define a fila 'door_commands' que este worker irá consumir.
task_queues = {
    'door_commands': {
        'exchange': 'default',
        'binding_key': 'door_commands',
    }
}

# Configurações adicionais podem ser incluídas aqui
result_backend = 'rpc://'
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'America/Sao_Paulo'
enable_utc = True