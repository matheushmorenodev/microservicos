# Funções de Injeção de Dependência
from fastapi import Request
from app.services.rpc_client import RPCClient

async def get_rpc_client(request: Request) -> RPCClient:
    """
    Dependência que cria e retorna uma instância do RPCClient.
    Ele pega o canal do RabbitMQ que foi armazenado no estado da aplicação.
    """
    channel = request.app.state.rabbitmq_channel
    return RPCClient(channel)