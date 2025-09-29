# middleware/app/rpc_client.py
import asyncio
import json
import uuid
from aio_pika import connect, Message, IncomingMessage

class RpcClient:
    def __init__(self, amqp_url):
        self.amqp_url = amqp_url
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.futures = {}

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

    async def call(self, task_name, payload):
        correlation_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.futures[correlation_id] = future

        message_body = {
            'id': correlation_id,
            'task': task_name,
            'args': [payload],
            'kwargs': {}
        }

        await self.channel.default_exchange.publish(
            Message(
                body=json.dumps(message_body).encode(),
                content_type='application/json',
                correlation_id=correlation_id,
                reply_to=self.callback_queue.name,
            ),
            routing_key='celery' # Fila padrão que o Celery ouve
        )
        return await future