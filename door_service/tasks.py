import os
import logging
import requests
from celery import Celery
from typing import Optional, List, Dict

# Importe o cliente do arquivo mqtt.py
from mqtt import MQTTBridgeClient

# =========================================================================================================
#                                 CONFIGURAÇÃO E CONSTANTES
# =========================================================================================================
# Celery App
app = Celery('door_service')
app.config_from_object('celeryconfig')

# MQTT e DB Service
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "emqx")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://db-service:8002/api")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================================================================
#                                 CLIENTE MQTT GLOBAL E EXCEÇÃO
# =========================================================================================================
logger.info("Criando instância global do cliente MQTT...")
mqtt_client = MQTTBridgeClient(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
mqtt_client.connect()

# MELHORIA AQUI: Exceção customizada para retentativas de conexão MQTT
class MQTTConnectionError(Exception):
    """Exceção para quando o cliente MQTT não está conectado."""
    pass

# =========================================================================================================
#                                 FUNÇÕES AUXILIARES
# =========================================================================================================
def call_db_service(endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
    """
    Realiza uma chamada GET ao serviço de banco de dados.
    Lança exceção em caso de erro para habilitar retentativas do Celery.
    """
    url = f"{DB_SERVICE_URL}/{endpoint}/"
    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Erro ao comunicar com db-service em {url}: {e}")
        # Relança a exceção para que as tarefas possam usar 'autoretry_for'
        raise e

def get_active_iot_topics() -> List[str]:
    """Obtém a lista de tópicos MQTT associados a IoTs ativos."""
    logger.info("Buscando IoTs ativos no db-service...")
    active_iots = call_db_service('iots', params={'is_active': 'true'})
    # O tópico 'status' é para receber dados do dispositivo
    topics = [f"campus/geral/{iot.get('name')}/status" for iot in active_iots if iot.get('name')]
    logger.info(f"{len(topics)} tópicos ativos encontrados para inscrição.")
    return topics

def send_log_task(level: str, message: str) -> None:
    """Envia uma mensagem de log para o log_service."""
    try:
        app.send_task(
            'save_log_task',
            args=['door_service', level.upper(), message],
            queue='log_queue'
        )
    except Exception as e:
        logger.error(f"CRITICAL: Falha ao enviar log para o log_service. Razão: {e}")

# =========================================================================================================
#                                 TAREFAS CELERY
# =========================================================================================================

# MELHORIA AQUI: Tornando a tarefa robusta a falhas de rede e MQTT
@app.task(
    name='process_command',
    autoretry_for=(MQTTConnectionError,), # Tenta novamente se o MQTT estiver desconectado
    retry_backoff=True,
    max_retries=10 # Tenta por mais tempo, pois a conexão MQTT pode demorar a voltar
)
def process_command(command_data: dict) -> Optional[str]:
    """Processa comandos recebidos da fila 'door_commands'."""
    
    # MELHORIA AQUI: Garante que estamos conectados antes de processar
    if not mqtt_client.is_connected():
        raise MQTTConnectionError("Cliente MQTT não está conectado. Aguardando reconexão...")

    action = command_data.get("action")
    topic = command_data.get("topic")
    
    log_message = f"Processando comando: {action}"
    if topic:
        log_message += f" para o tópico: {topic}"
    logger.info(log_message)
    
    try:
        if not topic:
            raise ValueError("Campo 'topic' é obrigatório para esta ação.")

        if action == "publish":
            payload = command_data.get("payload", "{}")
            qos = int(command_data.get("qos", 1))
            retain = bool(command_data.get("retain", False))
            mqtt_client.publish(topic, payload, qos, retain)
            send_log_task('INFO', f"Publicado em '{topic}': {payload}")

        elif action == "subscribe":
            qos = int(command_data.get("qos", 1))
            mqtt_client.subscribe(topic, qos)
            send_log_task('INFO', f"Inscrito no tópico: '{topic}'")
        
        elif action == "unsubscribe":
            mqtt_client.unsubscribe(topic)
            send_log_task('INFO', f"Inscrição cancelada no tópico: '{topic}'")

        elif action == "status":
            last_msg = mqtt_client.get_last_message(topic)
            logger.info(f"Retornando último status do tópico '{topic}': {last_msg}")
            return last_msg

        else:
            logger.warning(f"Ação desconhecida recebida: {action}")
            send_log_task('WARNING', f"Ação desconhecida: {action}")

    except Exception as e:
        logger.exception(f"Erro ao processar comando '{action}': {e}")
        send_log_task('ERROR', f"Erro ao processar comando '{action}': {e}")
        # Relançar a exceção pode ser útil para monitoramento
        raise

# MELHORIA AQUI: Tornando a tarefa de sincronização robusta
@app.task(
    name='sync_subscriptions',
    autoretry_for=(requests.RequestException,), # Tenta novamente se o db-service estiver offline
    retry_backoff=True,
    max_retries=5
)
def sync_subscriptions() -> str:
    """Garante que todos os tópicos de IoTs ativos estejam sincronizados no cliente MQTT."""
    logger.info("Sincronizando inscrições MQTT...")
    try:
        active_topics = get_active_iot_topics()
        if not active_topics:
            logger.warning("Nenhum tópico ativo encontrado para sincronizar.")
            return "Nenhum tópico ativo."
        
        # O cliente Paho MQTT lida com re-inscrições de forma inteligente
        for topic in active_topics:
            mqtt_client.subscribe(topic)
        
        message = f"{len(active_topics)} tópicos ativos sincronizados."
        send_log_task('INFO', message)
        return message
    except Exception as e:
        logger.exception("Falha crítica durante a sincronização de inscrições.")
        send_log_task('ERROR', f"Falha na sincronização de tópicos: {e}")
        raise

# =========================================================================================================
#                                 INICIALIZAÇÃO E TAREFAS PERIÓDICAS
# =========================================================================================================
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    logger.info("Worker inicializado. Executando sincronização inicial de tópicos MQTT.")
    # Executa a primeira sincronização na inicialização
    sender.add_periodic_task(10.0, sync_subscriptions.s(), name='Initial sync', expires=15)

    # MELHORIA AQUI: Ativando a tarefa periódica
    # Sincroniza a cada 5 minutos para pegar novos dispositivos ou mudanças de status
    sender.add_periodic_task(300.0, sync_subscriptions.s(), name='Sync subscriptions every 5 minutes')