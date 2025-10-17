import json
import time
import pika
from .logger import get_logger

logger = get_logger("RabbitMQConsumer")

class RabbitMQConsumer:
    def __init__(self, host: str, queue: str, mqtt_client, mqtt_manager) -> None:
        self.host = host
        self.queue = queue
        self.mqtt_client = mqtt_client
        self.manager = mqtt_manager
        self.connection = None
        self.channel = None

    def _connect(self) -> None:
        while True:
            try:
                logger.info(f"Conectando ao RabbitMQ em {self.host}...")
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.host))
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.queue, durable=True)
                logger.info(f"Conectado e fila '{self.queue}' declarada.")
                break
            except pika.exceptions.AMQPConnectionError:
                logger.warning("Falha na conexão. Tentando novamente em 5s...")
                time.sleep(5)

    def _process_message(self, ch, method, properties, body: bytes) -> None:
        try:
            message = json.loads(body)
            action = message.get("action")

            if not action:
                logger.error("Mensagem inválida: faltando campo 'action'.")
                return

            # 🔹 1. Ações MQTT básicas
            if action == "publish":
                topic = message.get("topic")
                payload = message.get("payload", "{}")
                qos = int(message.get("qos", 0))
                retain = bool(message.get("retain", False))
                self.mqtt_client.publish(topic, payload, qos, retain)

            elif action == "subscribe":
                topic = message.get("topic")
                qos = int(message.get("qos", 0))
                self.mqtt_client.subscribe(topic, qos)

            elif action == "status":
                topic = message.get("topic")
                last_message = self.mqtt_client.messages.get(topic)
                logger.info(f"Última mensagem no tópico '{topic}': {last_message}")

            # 🔹 2. Ações de controle de portas
            # elif action == "door_connect":
            #     self.manager.handle_door_connection(message["department"], message["name"])

            # elif action == "door_disconnect":
            #     self.manager.handle_door_disconnection(message["department"], message["name"])

            else:
                logger.warning(f"Ação desconhecida: {action}")

        except json.JSONDecodeError:
            logger.error("Erro ao decodificar JSON da mensagem.")
        except Exception as e:
            logger.exception(f"Erro inesperado ao processar mensagem: {e}")
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def start_consuming(self) -> None:
        self._connect()
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.queue, on_message_callback=self._process_message)
        logger.info(f"Aguardando mensagens na fila '{self.queue}'...")

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Encerrando consumo manualmente...")
        finally:
            self._close()

    def _close(self) -> None:
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Conexão RabbitMQ encerrada.")
