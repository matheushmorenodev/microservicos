import time
import paho.mqtt.client as mqtt
from .logger import get_logger

logger = get_logger("MQTTBridgeClient")

class MQTTBridgeClient:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="door_service"
        )
        self._setup_callbacks()
        self.last_messages = {}

    def _setup_callbacks(self) -> None:
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info("Conectado ao broker MQTT.")
        else:
            logger.error(f"Falha ao conectar. Código: {reason_code}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        logger.warning(f"Desconectado do broker MQTT. Código: {rc}")
        if rc != 0:
            logger.info("Tentando reconectar automaticamente...")
            self.connect()

    def _on_message(self, client, userdata, msg):
        decoded_payload = msg.payload.decode()
        self.last_messages[msg.topic] = decoded_payload
        logger.info(f"Mensagem recebida no tópico '{msg.topic}': {decoded_payload}")

    def connect(self) -> None:
        while True:
            try:
                logger.info(f"Conectando a {self.host}:{self.port}...")
                self.client.connect(self.host, self.port, keepalive=60)
                self.client.loop_start()
                break
            except Exception as e:
                logger.warning(f"Erro ao conectar: {e}. Tentando em 5s...")
                time.sleep(5)   

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> None:
        self.client.publish(topic, payload, qos, retain)
        logger.info(f"Publicado no tópico '{topic}': {payload}")

    def subscribe(self, topic: str, qos: int = 0) -> None:
        self.client.subscribe(topic, qos)
        logger.info(f"Inscrito no tópico '{topic}'")

    def unsubscribe(self, topic: str) -> None:
        self.client.unsubscribe(topic)
        self.last_messages.pop(topic, None)
        logger.info(f"Desinscrito do tópico '{topic}'")

    def get_last_message(self, topic: str) -> str | None:
        return self.last_messages.get(topic)

    def disconnect(self) -> None:
        self.client.loop_stop()
        logger.info("Desconectado do broker MQTT.")