from .config import RABBITMQ_HOST, RABBITMQ_QUEUE, MQTT_BROKER_HOST, MQTT_BROKER_PORT
from .mqtt_client import MQTTBridgeClient
from .mqtt_manager import MQTTManager
from .rabbit_consumer import RabbitMQConsumer
from .logger import get_logger

logger = get_logger("Main")

def main():
    logger.info("=== Iniciando serviço de ponte AMQP → MQTT com gerenciamento de portas ===")

    # 1️⃣ Inicia cliente MQTT
    mqtt_client = MQTTBridgeClient(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    mqtt_client.connect()

    # 2️⃣ Gerencia portas
    mqtt_manager = MQTTManager(mqtt_client)
    mqtt_manager.subscribe_active_doors()

    # 3️⃣ Inicia consumidor RabbitMQ
    rabbit_consumer = RabbitMQConsumer(RABBITMQ_HOST, RABBITMQ_QUEUE, mqtt_client, mqtt_manager)
    rabbit_consumer.start_consuming()

    # 4️⃣ Encerramento
    mqtt_client.disconnect()
    logger.info("=== Serviço encerrado ===")

if __name__ == "__main__":
    main()
