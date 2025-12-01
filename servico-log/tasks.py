import os
import logging
from celery import Celery
import requests

# =======================================================================================================================
#                                 Configuração
# =======================================================================================================================
# Configuração de logging padrão
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery App
app = Celery('log_service')
app.config_from_object('celeryconfig')

# URL do serviço de banco de dados, agora vinda de variáveis de ambiente
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://servico-banco-dados:8002/api")

# =======================================================================================================================
#                             Tarefas Celery principais do serviço de log
# =======================================================================================================================

@app.task(
    name='save_log_task',
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=5
)
def save_log_task(service_name, level, message, correlation_id=None):
    """
    Recebe dados de log e faz um POST para o db_service para salvá-los.
    Esta tarefa é robusta e tentará novamente se o db_service estiver offline.
    """
    try:
        payload = {
            "service_name": service_name,
            "level": level,
            "message": message,
            "correlation_id": correlation_id
        }
        url = f"{DB_SERVICE_URL}/logs/"
        response = requests.post(url, json=payload, timeout=5)
        
        response.raise_for_status() 
        
        logger.info(f"Log salvo: [{service_name}] {message}") # <--- 4. Usando logger

    except requests.RequestException as e:
        logger.warning(f"Falha de comunicação com db_service: {e}. Tentando novamente...")
        raise e
        
    except Exception as e:
        logger.exception(f"ERRO CRÍTICO AO SALVAR LOG (não será tentado novamente): {e}")