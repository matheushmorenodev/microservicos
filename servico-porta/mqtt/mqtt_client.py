import logging
import asyncio
from typing import Optional, Set, Dict, Callable, Awaitable
import aiomqtt 

logger = logging.getLogger("MQTTBridgeClient")

# Tipo para o callback de log (BridgeService._log)
LogCallback = Callable[[str, str], Awaitable[None]]

class AsyncMQTTBridgeClient:
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.client: Optional[aiomqtt.Client] = None
        
        # Armazena apenas o último status (para consultas rápidas via RPC)
        self.last_messages: Dict[str, str] = {}
        
        # Lista de tópicos dinâmicos (status) que devemos manter inscritos
        self.managed_subscriptions: Set[str] = set()
        
        self.log_callback: Optional[LogCallback] = None
        self._shutdown = False
        self.ready_event = asyncio.Event()

    def _send_log(self, level: str, message: str):
        """Dispara o callback de log (que envia para o RabbitMQ -> Banco)."""
        if self.log_callback:
            coro = self.log_callback(level, message)
            asyncio.create_task(coro)

    async def connect(self, log_callback: Optional[LogCallback] = None):
        """Loop principal: Conecta, Re-conecta e Escuta mensagens."""
        self.log_callback = log_callback
        self._shutdown = False
        logger.info(f"Iniciando MQTT Client em {self.host}:{self.port}...")

        while not self._shutdown:
            try:
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    identifier="door_service_bridge",
                    keepalive=120,
                    clean_session=True 
                ) as client:
                    
                    self.client = client
                    logger.info("MQTT Conectado.")
                    self._send_log("INFO", "Conexão MQTT estabelecida.")
                    
                    # 1. INSCRIÇÃO OBRIGATÓRIA NO TÓPICO GLOBAL DE LOGS
                    # Independente do banco de dados, sempre escutamos "log"
                    await self.client.subscribe("log", qos=1)
                    logger.info("Inscrito no canal global 'log'.")

                    # 2. Restaura inscrições dinâmicas (Status dos dispositivos)
                    if self.managed_subscriptions:
                        logger.info(f"Restaurando {len(self.managed_subscriptions)} inscrições de status...")
                        tasks = [self.client.subscribe(t, qos=1) for t in self.managed_subscriptions]
                        await asyncio.gather(*tasks, return_exceptions=True)

                    self.ready_event.set()
                    logger.info("Aguardando mensagens...")
                    
                    # 3. Loop de Mensagens
                    async for message in self.client.messages:
                        try:
                            topic = message.topic.value
                            payload = message.payload.decode()
                            
                            # --- ROTEAMENTO ---
                            
                            # CASO 1: Tópico Global de Logs
                            if topic == "log":
                                # Envia direto para o Banco de Dados
                                # Formato do log: [IoT Log Global] Payload
                                self._send_log("INFO", f"[IoT Log Global] {payload}")
                                logger.info(f"Log Global recebido: {payload}")
                            
                            # CASO 2: Tópicos de Status (Hierárquicos)
                            else:
                                # Salva no Cache Local para a API consultar
                                self.last_messages[topic] = payload
                                logger.info(f"Status Atualizado: {topic} = {payload}")

                        except Exception as e:
                            logger.error(f"Erro processando mensagem MQTT: {e}")
            
            except aiomqtt.MqttError as e:
                logger.error(f"Queda MQTT: {e}. Retentando em 5s...")
                self.ready_event.clear()
                self.client = None
                await asyncio.sleep(5)
            
            except asyncio.CancelledError:
                logger.info("MQTT cancelado.")
                self._shutdown = True
            
            except Exception as e:
                logger.critical(f"Erro fatal MQTT: {e}", exc_info=True)
                self.ready_event.clear()
                self.client = None
                if not self._shutdown: await asyncio.sleep(5)

        self.client = None
        self.ready_event.clear()

    async def _wait_for_ready(self, timeout: float = 10.0):
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise ConnectionError("MQTT Client não está pronto.")
        if not self.client:
            raise ConnectionError("MQTT Client desconectado.")

    async def disconnect(self):
        logger.info("Desconectando MQTT...")
        self._shutdown = True
        self.ready_event.clear()
        self.client = None

    async def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False):
        await self._wait_for_ready()
        await self.client.publish(topic, payload, qos, retain)
        logger.info(f"Publicado: {topic}")

    async def subscribe(self, topic: str, qos: int = 1, managed: bool = True):
        await self._wait_for_ready()
        await self.client.subscribe(topic, qos)
        if managed:
            self.managed_subscriptions.add(topic)
        logger.info(f"Inscrito: {topic}")

    async def unsubscribe(self, topic: str):
        await self._wait_for_ready()
        await self.client.unsubscribe(topic)
        self.managed_subscriptions.discard(topic)
        self.last_messages.pop(topic, None)
        logger.info(f"Desinscrito: {topic}")

    async def sync_subscriptions(self, topics_from_db: Set[str]):
        """
        Sincroniza apenas os tópicos de STATUS vindos do banco.
        O tópico 'log' já é assinado fixamente no connect().
        """
        try:
            await self._wait_for_ready()
        except ConnectionError:
             return

        # Filtra o que já temos para não duplicar chamadas
        new_topics = topics_from_db - self.managed_subscriptions
        
        # Removemos inscrições no tópico 'log' daqui, pois ele é fixo/global
        if "log" in new_topics:
            new_topics.remove("log")

        if new_topics:
            tasks = []
            for topic in new_topics:
                logger.info(f"Sync: Assinando '{topic}'")
                tasks.append(self.subscribe(topic, qos=1, managed=True)) 
            
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            logger.info("Sync: Nenhuma nova inscrição necessária.")

    def get_last_message(self, topic: str) -> Optional[str]:
        return self.last_messages.get(topic)