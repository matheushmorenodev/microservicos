import json
from asyncio import Future
from typing import Any, Coroutine, Optional
import uuid
from aio_pika import connect, Message, IncomingMessage, Message, ExchangeType

class RpcClient:
    def __init__(self, amqp_url):
        self.amqp_url = amqp_url
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.futures = {}
        self.default_queue_name = 'celery' 

    async def connect(self):
        self.connection = await connect(self.amqp_url)
        self.channel = await self.connection.channel()
        self.callback_queue = await self.channel.declare_queue(exclusive=True)
        await self.callback_queue.consume(self.on_response)
        return self

    def on_response(self, message: IncomingMessage):
        future = self.futures.pop(message.correlation_id, None)
        if future:
            future.set_result(json.loads(message.body))
            
    async def call(
            self, task_name: str, payload: Any, queue: Optional[str] = None
        ) -> Coroutine[Any, Any, Any]:
            
            if self.channel is None:
                raise RuntimeError("A conexão com o RabbitMQ não está ativa.")

            correlation_id = str(uuid.uuid4())
            future = self.futures[correlation_id] = Future()

            # O 'routing_key' será a fila de destino
            routing_key = queue or self.default_queue_name

            message_body = {
                'id': correlation_id,
                'task': task_name,
                'args': payload if isinstance(payload, (list, tuple)) else [payload],
                'kwargs': {}
            }

            await self.channel.default_exchange.publish(
                Message(
                    json.dumps(message_body).encode(),
                    content_type='application/json',
                    correlation_id=correlation_id,
                    reply_to=self.callback_queue.name,
                ),
                routing_key=routing_key, # Usa a fila correta
            )

            return await future