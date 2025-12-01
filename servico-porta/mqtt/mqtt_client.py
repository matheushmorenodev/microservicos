# servico-porta/mqtt/mqtt_client.py

import logging
import asyncio
from typing import Optional, Set, Dict, Callable, Awaitable
import aiomqtt  # <--- MUDANÇA

logger = logging.getLogger("MQTTBridgeClient")

# Tipo para o callback de log (continua o mesmo)
LogCallback = Callable[[str, str], Awaitable[None]]

class AsyncMQTTBridgeClient:
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        # O cliente agora é do tipo aiomqtt.Client
        self.client: Optional[aiomqtt.Client] = None
        
        self.last_messages: Dict[str, str] = {}
        self.managed_subscriptions: Set[str] = set()
        self.log_callback: Optional[LogCallback] = None
        self._shutdown = False
        
        # Evento para sinalizar que o cliente está pronto para operações
        self.ready_event = asyncio.Event()

    def _send_log(self, level: str, message: str):
        """Helper interno para enviar logs se o callback estiver configurado."""
        if self.log_callback:
            # Pega a corotina (do lambda) e agenda como uma tarefa
            coro = self.log_callback(level, message)
            asyncio.create_task(coro)

    async def connect(self, log_callback: Optional[LogCallback] = None):
        """
        Tarefa principal: conecta, ouve mensagens e lida com reconexões.
        Esta única tarefa substitui 'connect' e 'message_listener'.
        """
        self.log_callback = log_callback
        self._shutdown = False
        logger.info(f"Iniciando loop principal do MQTT com {self.host}:{self.port}...")

        while not self._shutdown:
            try:
                # O 'async with' do aiomqtt gerencia a conexão e reconexão
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    identifier="door_service_bridge",
                    keepalive=120,
                    # Habilita limpeza de sessão, mas re-inscrição automática
                    clean_session=True 
                ) as client:
                    
                    self.client = client
                    logger.info("Conectado ao broker MQTT com sucesso.")
                    self._send_log("INFO", "Conectado ao broker MQTT.")
                    
                    # Restaurar inscrições gerenciadas
                    # aiomqtt re-inscreve automaticamente após reconexões,
                    # mas precisamos nos inscrever na primeira vez.
                    if self.managed_subscriptions:
                        logger.info(f"Restaurando {len(self.managed_subscriptions)} inscrições...")
                        tasks = [
                            self.client.subscribe(topic, qos=1) 
                            for topic in self.managed_subscriptions
                        ]
                        await asyncio.gather(*tasks, return_exceptions=True)
                        logger.info("Inscrições restauradas.")

                    # Sinaliza para outros métodos (publish/subscribe) que estamos prontos
                    self.ready_event.set()

                    # Loop principal de mensagens (substitui message_listener)
                    logger.info("Listener de mensagens iniciado.")
                    async for message in self.client.messages:
                        try:
                            topic = message.topic.value
                            payload = message.payload.decode()
                            logger.info(f"Mensagem recebida - Tópico: '{topic}', Payload: {payload}")
                            self.last_messages[topic] = payload
                        except Exception as e:
                            logger.error(f"Erro ao processar mensagem MQTT: {e}")
            
            except aiomqtt.MqttError as e:
                logger.error(f"Erro de conexão MQTT: {e}. Tentando novamente em 5s...")
                self.ready_event.clear() # Sinaliza que não estamos prontos
                self.client = None
                await asyncio.sleep(5) # Aguarda antes de tentar recriar o 'async with'
            
            except asyncio.CancelledError:
                logger.info("Loop principal do MQTT cancelado.")
                self._shutdown = True # Garante que o loop while termine
            
            except Exception as e:
                logger.critical(f"Erro fatal no loop MQTT: {e}", exc_info=True)
                self.ready_event.clear()
                self.client = None
                if not self._shutdown:
                    await asyncio.sleep(5)

        # Limpeza final
        self.client = None
        self.ready_event.clear()
        logger.info("Loop principal do MQTT encerrado.")

    async def _wait_for_ready(self, timeout: float = 10.0):
        """Aguarda o cliente estar conectado e pronto."""
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error("Timeout aguardando cliente MQTT ficar pronto.")
            raise ConnectionError("Cliente MQTT não está conectado ou pronto a tempo.")
            
        if not self.client:
            raise ConnectionError("Cliente MQTT não está conectado.")

    async def disconnect(self):
        """Sinaliza para o loop principal (connect) encerrar."""
        logger.info("Desconectando do broker MQTT...")
        self._shutdown = True
        self.ready_event.clear()
        self.client = None
        # A tarefa 'connect' vai pegar o _shutdown=True e sair
        # do loop, o que vai fechar o 'async with' e desconectar.
        logger.info("Sinal de shutdown do MQTT enviado.")

    async def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False):
        await self._wait_for_ready() # Espera o cliente estar pronto
        await self.client.publish(topic, payload, qos, retain)
        logger.info(f"Publicado - Tópico: '{topic}', Payload: {payload}")

    async def subscribe(self, topic: str, qos: int = 1, managed: bool = True):
        """Se inscreve em um tópico. 'managed=True' adiciona à lista de auto-reconexão."""
        await self._wait_for_ready() # Espera o cliente estar pronto
        
        await self.client.subscribe(topic, qos)
        if managed:
            self.managed_subscriptions.add(topic)
        logger.info(f"Inscrito no tópico: '{topic}' (Gerenciado: {managed})")

    async def unsubscribe(self, topic: str):
        await self._wait_for_ready() # Espera o cliente estar pronto
            
        await self.client.unsubscribe(topic)
        self.managed_subscriptions.discard(topic)
        self.last_messages.pop(topic, None)
        logger.info(f"Inscrição cancelada no tópico: '{topic}'")

    async def sync_subscriptions(self, topics_from_db: Set[str]):
        """Sincroniza as inscrições gerenciadas com a lista vinda do banco."""
        try:
            await self._wait_for_ready() # Espera o cliente estar pronto
        except ConnectionError:
             logger.warning("Não é possível sincronizar: cliente MQTT desconectado.")
             return

        topics_to_add = topics_from_db - self.managed_subscriptions
        # topics_to_remove = self.managed_subscriptions - topics_from_db
        
        tasks = []
        for topic in topics_to_add:
            logger.info(f"Sincronizando: Adicionando inscrição '{topic}'")
            # Adiciona 'managed=True' para garantir que seja salvo
            tasks.append(self.subscribe(topic, qos=1, managed=True)) 
            
        # for topic in topics_to_remove:
        #     logger.info(f"Sincronizando: Removendo inscrição '{topic}'")
        #     tasks.append(self.unsubscribe(topic))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.info("Sincronização: Nenhuma alteração de inscrição necessária.")

    def get_last_message(self, topic: str) -> Optional[str]:
        return self.last_messages.get(topic)
        
    def get_all_last_messages(self) -> Dict[str, str]:
        return self.last_messages