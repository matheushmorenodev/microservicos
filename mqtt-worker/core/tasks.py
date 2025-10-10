from celery import shared_task
from celery.signals import worker_ready
from .mqtt_client import MQTTClient

mqtt_client_instance = None

def get_mqtt_client():
    """Garante que temos apenas uma instância do cliente MQTT por processo."""
    global mqtt_client_instance
    if mqtt_client_instance is None:
        mqtt_client_instance = MQTTClient()
    return mqtt_client_instance


@worker_ready.connect
def start_mqtt_client(sender=None, **kwargs):
    """
    Este sinal é emitido apenas uma vez, quando o processo principal do Celery está pronto.
    Assim, criamos uma única conexão MQTT global para este worker.
    """
    print("Worker principal pronto. Iniciando cliente MQTT global...")
    client = get_mqtt_client()
    client.start()  # conecta e inicia o loop MQTT


@shared_task(name='send_mqtt_command')
def send_mqtt_command(topic, payload):
    """
    Task chamada pelo middleware para enviar comandos MQTT.
    """
    try:
        client = get_mqtt_client()
        client.publish_message(topic, payload)
        print(f"Mensagem MQTT publicada: {topic} -> {payload}")
        return {"status": "Comando enviado com sucesso", "topic": topic, "payload": payload}
    except Exception as e:
        print(f"ERRO ao enviar comando MQTT: {e}")
        return {"status": "erro", "detail": str(e)}
