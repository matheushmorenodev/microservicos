# door_service_teste/config.py
import os

# RabbitMQ / AMQP
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

# Filas AMQP
AMQP_COMMAND_QUEUE = "door_commands"
AMQP_LOG_QUEUE = "log_queue"

# MQTT
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "emqx")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# DB Service
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://db-service:8002/api")

# Bridge Service
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", 300)) # 5 minutos
