from celery import shared_task
from celery.signals import worker_process_init
from .mqtt_client import MQTTClient

mqtt_client_instance = None

def get_mqtt_client():
    """Garante que temos apenas uma instância do cliente MQTT por processo."""
    global mqtt_client_instance
    if mqtt_client_instance is None:
        mqtt_client_instance = MQTTClient()
    return mqtt_client_instance

@worker_process_init.connect
def start_mqtt_client(**kwargs):
    """
    Esta função é chamada automaticamente quando um processo do worker Celery inicia.
    É o lugar perfeito para iniciar nossa conexão MQTT em segundo plano.
    """
    print("Processo do worker iniciado. Iniciando cliente MQTT...")
    client = get_mqtt_client()
    client.start()

@shared_task(name='send_mqtt_command')
def send_mqtt_command(topic, payload):
    """
    Esta é a tarefa que será chamada pelo middleware para enviar um comando.
    """
    try:
        client = get_mqtt_client()
        client.publish_message(topic, payload)
        return {"status": "Comando enviado com sucesso", "topic": topic, "payload": payload}
    except Exception as e:
        print(f"ERRO ao enviar comando MQTT: {e}")
        return {"status": "erro", "detail": str(e)}