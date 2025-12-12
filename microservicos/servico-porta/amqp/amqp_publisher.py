# servico-porta/amqp/amqp_publisher.py
import json
import logging
import aio_pika
from typing import Dict, Any

logger = logging.getLogger("AMQPPublisher")

class AMQPPublisher:
    """Helper para publicar mensagens compatíveis com Celery."""
    
    def __init__(self, connection: aio_pika.RobustConnection, queue_name: str):
        self.connection = connection
        self.queue_name = queue_name
        self.channel = None

    async def setup(self):
        """Declara o canal e a fila."""
        try:
            self.channel = await self.connection.channel()
            # Declara a fila para garantir que ela existe
            await self.channel.declare_queue(self.queue_name, durable=True)
            logger.info(f"Publisher configurado para fila '{self.queue_name}'")
        except Exception as e:
            logger.error(f"Erro ao configurar publisher AMQP: {e}")

    async def publish(self, data: Dict[str, Any]):
        """Publica mensagem com Content-Type JSON (Obrigatório para Celery)."""
        if not self.channel:
            await self.setup()
            
        if not self.channel:
            logger.error("Canal AMQP não disponível.")
            return

        try:
            message_body = json.dumps(data).encode('utf-8')
            
            await self.channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    # Estes headers são vitais para o Celery Worker aceitar a mensagem
                    content_type='application/json',
                    content_encoding='utf-8'
                ),
                routing_key=self.queue_name
            )
        except Exception as e:
            logger.error(f"Erro ao publicar mensagem na fila '{self.queue_name}': {e}")
            # Tenta reconectar o canal na próxima
            self.channel = None

    async def close(self):
        if self.channel:
            await self.channel.close()