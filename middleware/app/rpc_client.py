# middleware/app/rpc_client.py

import json
import asyncio
import logging
from asyncio import Future
from typing import Any, Coroutine, Optional
import uuid
from aio_pika import connect, Message, IncomingMessage, DeliveryMode
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue
from aiormq.exceptions import AMQPError, ChannelInvalidStateError, ConnectionClosed
from fastapi import HTTPException

# Use o logger em vez de print
logger = logging.getLogger(__name__)

class RpcClient:
    def __init__(self, amqp_url):
        self.amqp_url = amqp_url
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.callback_queue: Optional[AbstractQueue] = None
        self.futures: dict[str, Future] = {}
        # Lock para evitar que várias requisições tentem reconectar ao mesmo tempo
        self._connect_lock = asyncio.Lock()
        self.default_queue_name = 'celery' # Mantendo seu padrão

    @property
    def is_connected(self) -> bool:
        """Verifica se a conexão está ativa."""
        return self.connection is not None and not self.connection.is_closed

    async def close(self):
        """Fecha a conexão e o canal de forma limpa."""
        async with self._connect_lock:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
            self.connection = None
            self.channel = None
            self.callback_queue = None
            self.futures.clear()

    async def connect(self):
        """Estabelece a conexão e o canal, de forma idempotente."""
        # Se já estiver conectado, não faz nada
        if self.is_connected:
            return

        # Usa um lock para que apenas uma corotina tente conectar
        async with self._connect_lock:
            # Verifica novamente caso outra corotina tenha conectado enquanto esperava o lock
            if self.is_connected:
                return

            logger.info("RPC Client: Conectando ao RabbitMQ...")
            try:
                self.connection = await connect(self.amqp_url, timeout=5)
                self.channel = await self.connection.channel()
                
                # Fila de callback exclusiva, que será deletada quando a conexão fechar
                self.callback_queue = await self.channel.declare_queue(
                    exclusive=True, auto_delete=True
                )
                
                # Começa a consumir da fila de callback. 
                # no_ack=False é o padrão, o que é bom (vamos fazer ack manual)
                await self.callback_queue.consume(self.on_response)
                
                logger.info("RPC Client: Conectado e fila de callback pronta.")
            except Exception as e:
                logger.error(f"RPC Client: Falha ao conectar: {e}")
                # Limpa o estado para permitir nova tentativa
                self.connection = None
                self.channel = None
                self.callback_queue = None
                raise

    async def on_response(self, message: IncomingMessage):
        """Processa a mensagem de resposta recebida."""
        future = self.futures.pop(message.correlation_id, None)
        
        try:
            if future:
                future.set_result(json.loads(message.body))
            else:
                logger.warning(f"RPC Client: Resposta recebida para correlation_id desconhecido: {message.correlation_id}")
        finally:
            # IMPORTANTE: Confirma (Ack) a mensagem para o RabbitMQ.
            # Isso evita o timeout de 30 minutos.
            await message.ack()

    async def _ensure_connection(self):
        """Garante que a conexão está ativa antes de uma operação."""
        if not self.is_connected:
            await self.connect()

    async def call(self, task_name: str, payload: Any, queue: Optional[str] = None) -> Any:
        """
        Executa a chamada RPC com lógica de reconexão automática.
        """
        try:
            # Garante que estamos conectados antes de tentar publicar
            await self._ensure_connection()
            return await self._publish_message(task_name, payload, queue)
        
        except (ConnectionClosed, ChannelInvalidStateError, AMQPError, AttributeError, RuntimeError) as e:
            # Se algo deu errado (conexão caiu, canal fechou),
            # limpamos a conexão e tentamos UMA vez novamente.
            logger.warning(f"RPC Client: Conexão perdida. Tentando reconectar. Erro: {e}")
            
            # Força o fechamento e limpeza
            await self.close() 
            
            # Tenta conectar e enviar novamente
            try:
                await self._ensure_connection()
                return await self._publish_message(task_name, payload, queue)
            except Exception as e_final:
                logger.error(f"RPC Client: Falha ao enviar mensagem após reconexão: {e_final}")
                raise HTTPException(status_code=503, detail="Serviço indisponível (Message Broker)")

    async def _publish_message(self, task_name: str, payload: Any, queue: Optional[str]) -> Any:
        """Lógica interna de publicação da mensagem."""
        
        if not self.channel or not self.callback_queue:
            raise RuntimeError("RPC Client não está inicializado corretamente.")

        correlation_id = str(uuid.uuid4())
        future = self.futures[correlation_id] = Future()

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
            routing_key=routing_key,
        )

        try:
            # Adiciona um timeout de 10 segundos para a resposta
            return await asyncio.wait_for(future, timeout=10.0)
        except asyncio.TimeoutError:
            logger.error(f"RPC Client: Timeout esperando pela resposta da tarefa '{task_name}' (ID: {correlation_id})")
            # Remove a future para não vazar memória
            self.futures.pop(correlation_id, None)
            raise HTTPException(status_code=504, detail="Timeout: A tarefa demorou muito para responder.")
    
    async def publish_fire_and_forget(self, task_name: str, payload: Any, queue: Optional[str] = None):
        """
        Publica uma tarefa no estilo 'Fire and Forget' (sem esperar resposta).
        """
        
        # Garante que estamos conectados
        try:
            await self._ensure_connection()
        except Exception as e:
            logger.error(f"Publicador [F/F]: Falha ao garantir conexão: {e}")
            raise HTTPException(status_code=503, detail="Serviço indisponível (Message Broker)")

        if not self.channel:
             raise RuntimeError("RPC Client não está inicializado corretamente.")

        correlation_id = str(uuid.uuid4())
        routing_key = queue or self.default_queue_name

        message_body = {
            'id': correlation_id,
            'task': task_name,
            'args': payload if isinstance(payload, (list, tuple)) else [payload],
            'kwargs': {}
        }

        try:
            # Publica a mensagem sem 'reply_to'
            await self.channel.default_exchange.publish(
                Message(
                    json.dumps(message_body).encode(),
                    content_type='application/json',
                    correlation_id=correlation_id,
                    delivery_mode=DeliveryMode.PERSISTENT
                ),
                routing_key=routing_key,
            )
            logger.info(f"Publicada tarefa [Fire/Forget] '{task_name}' (ID: {correlation_id}) para fila '{routing_key}'")
        
        except (ConnectionClosed, ChannelInvalidStateError, AMQPError, RuntimeError) as e:
            logger.warning(f"Publicador [F/F]: Conexão perdida. Tentando reconectar. Erro: {e}")
            # Limpa a conexão para forçar reconexão na próxima tentativa
            await self.close() 
            # Para F/F, podemos falhar rápido aqui e deixar o HTTP 500
            # A alternativa seria tentar publicar novamente, como no 'call',
            # mas isso pode atrasar o webhook.
            raise HTTPException(status_code=503, detail="Serviço indisponível (Message Broker) ao tentar publicar.")
        
        except Exception as e:
            logger.error(f"Publicador [F/F]: Erro inesperado ao publicar: {e}")
            raise HTTPException(status_code=500, detail="Erro interno do publicador.")