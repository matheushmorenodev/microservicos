# mqtt.py

import logging
import paho.mqtt.client as mqtt
from typing import Optional

logger = logging.getLogger(__name__)

class MQTTBridgeClient:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.last_messages = {}
        # Usamos uma versão mais recente da API de callback para clareza
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="door_service")
        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            logger.info("Conectado com sucesso ao broker MQTT.")
        else:
            logger.error(f"Falha ao conectar ao broker MQTT. Código de erro: {reason_code}")

    def _on_disconnect(self, client, userdata, reason_code, properties=None) -> None:
        # A biblioteca paho-mqtt tentará reconectar automaticamente em background
        logger.warning(f"Desconectado do broker MQTT (código: {reason_code}). Aguardando reconexão automática.")

    def _on_message(self, client, userdata, msg) -> None:
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            logger.info(f"Mensagem recebida - Tópico: '{topic}', Payload: {payload}")
            self.last_messages[topic] = payload
        except Exception as e:
            logger.error(f"Erro ao processar mensagem MQTT recebida: {e}")

    def connect(self) -> None:
        try:
            logger.info(f"Conectando ao broker MQTT em {self.host}:{self.port}...")
            # connect_async é não-bloqueante
            self.client.connect_async(self.host, self.port, keepalive=60)
            self.client.loop_start() # Inicia a thread de rede em background
        except Exception as e:
            logger.exception(f"Erro ao iniciar conexão com o broker MQTT: {e}")

    # MELHORIA AQUI: Método para verificar o estado da conexão
    def is_connected(self) -> bool:
        """Verifica se o cliente MQTT está atualmente conectado."""
        return self.client.is_connected()

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False) -> None:
        self.client.publish(topic, payload, qos, retain)
        logger.info(f"Publicado - Tópico: '{topic}', Payload: {payload}")

    def subscribe(self, topic: str, qos: int = 1) -> None:
        self.client.subscribe(topic, qos)
        logger.info(f"Inscrito no tópico: '{topic}'")
        
    def unsubscribe(self, topic: str) -> None:
        self.client.unsubscribe(topic)
        logger.info(f"Cancelada inscrição no tópico: '{topic}'")
        # Opcional: Remove do cache de últimas mensagens
        if topic in self.last_messages:
            del self.last_messages[topic]
            logger.info(f"Removido cache do tópico: '{topic}'")

    def get_last_message(self, topic: str) -> Optional[str]:
        return self.last_messages.get(topic)