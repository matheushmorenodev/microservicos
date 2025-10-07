from celery import shared_task
import requests

DB_SERVICE_URL = "http://db-service:8002/api"

@shared_task(name='save_log_task')
def save_log_task(service_name, level, message, correlation_id=None):
    """
    Recebe dados de log e faz um POST para o db_service para salvá-los.
    """
    try:
        payload = {
            "service_name": service_name,
            "level": level,
            "message": message,
            "correlation_id": correlation_id
        }
        response = requests.post(f"{DB_SERVICE_URL}/logs/", json=payload, timeout=5)
        response.raise_for_status() # Lança erro se a resposta for 4xx ou 5xx
        print(f"Log salvo com sucesso: [{service_name}] {message}")
    except requests.RequestException as e:
        print(f"ERRO CRÍTICO AO SALVAR LOG: Falha de comunicação com db_service. {e}")
    except Exception as e:
        print(f"ERRO CRÍTICO AO SALVAR LOG: {e}")