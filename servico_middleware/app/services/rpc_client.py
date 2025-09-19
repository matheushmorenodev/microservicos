# Lógica do cliente RPC totalmente isolada

import asyncio
import json
import uuid
from typing import Dict, Optional

import aio_pika
from aio_pika.abc import AbstractChannel

# O asyncio.Future é um objeto que serve como um "placeholder" para um resultado 
# que ainda não está disponível. É a peça central para "esperar" pela resposta.
Future = asyncio.Future

class RPCClient:
    """
    Uma classe que encapsula a lógica de chamada de procedimento remoto (RPC)
    sobre o RabbitMQ.

    Ela gerencia a criação de uma fila de resposta exclusiva, o rastreamento de
    requisições pendentes usando 'correlation_id' e a espera assíncrona
    pelas respostas.
    """

    def __init__(self, channel: AbstractChannel):
        """
        Inicializa o cliente RPC.

        :param channel: Um canal de comunicação `aio_pika` já estabelecido.
        """
        self.channel = channel
        
        # Dicionário para mapear um correlation_id a uma Future.
        # Quando uma resposta com um certo correlation_id chega, sabemos qual
        # Future (e, portanto, qual chamada pendente) deve ser resolvida.
        self.futures: Dict[str, Future] = {}
        
        # O nome da fila exclusiva para onde os workers devem enviar as respostas.
        # Será definido durante a inicialização.
        self.callback_queue: Optional[aio_pika.abc.AbstractQueue] = None

    async def _initialize(self):
        """
        Realiza a configuração inicial necessária para o cliente RPC funcionar,
        principalmente a criação da fila de callback exclusiva.
        """
        if self.callback_queue is not None:
            return

        # 'exclusive=True' garante que apenas esta conexão pode usar a fila,
        # e ela será deletada quando a conexão for fechada. Isso é perfeito
        # para filas de resposta.
        self.callback_queue = await self.channel.declare_queue(exclusive=True)

        # Começa a consumir mensagens da fila de callback. A função _on_response
        # será chamada para cada mensagem recebida.
        await self.callback_queue.consume(self._on_response, no_ack=True)

    def _on_response(self, message: aio_pika.IncomingMessage):
        """
        Callback executado quando uma mensagem de resposta é recebida.
        """
        correlation_id = message.correlation_id
        if correlation_id is None:
            print(f"Recebida mensagem sem correlation_id. Ignorando.")
            return

        # Encontra a Future correspondente no dicionário de futuros pendentes.
        future = self.futures.pop(correlation_id, None)

        if future:
            # Se encontramos uma Future, "resolvemos" ela com o corpo da mensagem.
            # Isso vai "desbloquear" a chamada `await` no método 'call'.
            future.set_result(message.body)
        else:
            print(f"Recebida resposta para um correlation_id desconhecido ou que já expirou: {correlation_id}")


    async def call(self, queue_name: str, message_body: dict, timeout: int = 10) -> bytes:
        """
        Executa a chamada RPC.

        :param queue_name: O nome da fila para a qual a requisição será enviada.
        :param message_body: Um dicionário Python com os dados da requisição.
        :param timeout: Tempo em segundos para esperar pela resposta.
        :return: O corpo da mensagem de resposta em bytes.
        :raises asyncio.TimeoutError: Se a resposta não chegar dentro do timeout.
        """
        # Garante que a fila de callback está configurada antes de prosseguir.
        await self._initialize()

        # Gera um ID único para esta requisição específica.
        correlation_id = str(uuid.uuid4())
        
        # Cria a Future que atuará como o "placeholder" da resposta.
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self.futures[correlation_id] = future

        print(f"[*] Enviando requisição RPC para '{queue_name}' com ID: {correlation_id}")

        # Publica a mensagem na fila do worker.
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message_body).encode("utf-8"),
                correlation_id=correlation_id,
                # Propriedade crucial: informa ao worker para qual fila ele
                # deve enviar a resposta.
                reply_to=self.callback_queue.name, 
            ),
            routing_key=queue_name,
        )

        try:
            # A execução "pausa" aqui e espera até que a Future seja resolvida
            # (pelo método _on_response) ou até que o timeout seja atingido.
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            # Se o timeout ocorrer, removemos a Future do dicionário para
            # evitar vazamentos de memória e levantamos o erro novamente.
            self.futures.pop(correlation_id, None)
            raise