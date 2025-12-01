# servico-porta/amqp/amqp_publisher.py
import json
import logging
import aio_pika
from typing import Dict, Any

logger = logging.getLogger("AMQPPublisher")

class AMQPPublisher:
    """Helper para publicar mensagens em uma fila AMQP específica."""
    
    def __init__(self, connection: aio_pika.RobustConnection, queue_name: str):
        self.connection = connection
        self.queue_name = queue_name
        self.channel: Optional[aio_pika.abc.AbstractChannel] = None
        self.queue: Optional[aio_pika.abc.AbstractQueue] = None

    async def setup(self):
        """Declara o canal e a fila."""
        try:
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue(
                self.queue_name,
                durable=True
            )
            logger.info(f"Publisher configurado para fila '{self.queue_name}'")
        except Exception as e:
            logger.error(f"Erro ao configurar publisher AMQP: {e}")
            raise

    async def publish(self, data: Dict[str, Any]):
        """Publica uma mensagem na fila."""
        if not self.channel or not self.queue:
            raise ConnectionError("Publisher AMQP não está configurado. Chame setup()")
            
        try:
            message_body = json.dumps(data).encode()
            await self.channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=self.queue_name
            )
        except Exception as e:
            logger.error(f"Erro ao publicar mensagem na fila '{self.queue_name}': {e}")
            # Tentar re-estabelecer o canal em caso de falha
            await self.setup()

    async def close(self):
        """Fecha o canal."""
        if self.channel:
            await self.channel.close()
