from celery import shared_task
import requests
import time
from servico_permissao.celery import app as celery_app
DB_SERVICE_URL = "http://db-service:8002/api"

def ensure_user_exists(user_data):
    """
    Função auxiliar que garante que o usuário do token existe no db_service.
    Usa o método PATCH, que cria se não existir ou atualiza se já existir.
    """
    user_id = user_data.get('id')
    if not user_id:
        return

    # Dados que queremos garantir que estão no banco
    data_to_sync = {
        'user_id': user_id,
        'username': user_data.get('username'),
        'role': user_data.get('tipo_vinculo', 'Aluno') # Default para 'Aluno' se não vier no token
    }
    
    try:
        # Usamos o endpoint /api/users/{user_id}/. O DRF ViewSet lida com isso.
        # O método PATCH é ideal aqui: ele atualiza um recurso existente ou pode ser configurado para criar.
        # Vamos usar o método PUT para uma abordagem mais simples de get_or_create no backend.
        requests.put(f"{DB_SERVICE_URL}/users/{user_id}/", json=data_to_sync, timeout=5)
    except requests.RequestException as e:
        # Se a sincronização falhar, apenas logamos, mas não paramos o fluxo principal
        print(f"AVISO: Falha ao sincronizar usuário {user_id}: {e}")

def call_db_service(endpoint, params=None):
    """Função auxiliar para fazer chamadas GET ao db-service."""
    try:
        response = requests.get(f"{DB_SERVICE_URL}/{endpoint}/", params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Retorna um dicionário de erro em vez de levantar uma exceção
        return {'error': f'Erro de comunicação com o serviço de banco de dados: {e}'}
    except Exception as e:
        return {'error': f'Erro inesperado: {e}'}

def log_task(correlation_id, level, action, status, details=""):
    """Função auxiliar para enviar logs padronizados."""
    log_message = f"Action: {action}. Status: {status}. {details}"
    celery_app.send_task(
        'save_log_task', 
        args=['permission-worker', level, log_message, correlation_id],
        queue='log_queue'
    )

@shared_task(name='list_departments_task', bind=True)
def list_departments_task(self, user_data):
    start_time = time.time()
    user_id = user_data.get('id')
    username = user_data.get('username')
    user_role = user_data.get('tipo_vinculo')
    source_ip = user_data.get('source_ip', 'N/A')
    correlation_id = self.request.id

    log_details_start = f"User: {user_id} ({username}, {user_role}). Source IP: {source_ip}."
    log_task(correlation_id, 'INFO', 'list_departments', 'STARTED', log_details_start)

    try:
        if user_role == 'Servidor':
            result_data = call_db_service('departments')
        else:
            result_data = call_db_service('departments', params={'user_id': user_id})

        if isinstance(result_data, dict) and 'error' in result_data:
            raise Exception(result_data['error'])

        duration = (time.time() - start_time) * 1000
        log_details_end = f"Result: {len(result_data)} departments found. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'INFO', 'list_departments', 'SUCCESS', log_details_end)
        
        return result_data

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_details_error = f"Reason: {e}. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'ERROR', 'list_departments', 'FAILURE', log_details_error)
        return {'error': str(e)}


@shared_task(name='list_rooms_task', bind=True)
def list_rooms_task(self, user_data, department_pk):
    start_time = time.time()
    user_id = user_data.get('id')
    username = user_data.get('username')
    user_role = user_data.get('tipo_vinculo')
    source_ip = user_data.get('source_ip', 'N/A')
    correlation_id = self.request.id

    log_details_start = f"User: {user_id} ({username}, {user_role}). Source IP: {source_ip}. Resource: department_id={department_pk}."
    log_task(correlation_id, 'INFO', 'list_rooms', 'STARTED', log_details_start)

    try:
        params = {'department_pk': department_pk}
        if user_role != 'Servidor':
            params['user_id'] = user_id
        
        result_data = call_db_service('rooms', params=params)
        
        if isinstance(result_data, dict) and 'error' in result_data:
            raise Exception(result_data['error'])

        duration = (time.time() - start_time) * 1000
        log_details_end = f"Result: {len(result_data)} rooms found. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'INFO', 'list_rooms', 'SUCCESS', log_details_end)
        
        return result_data

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_details_error = f"Reason: {e}. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'ERROR', 'list_rooms', 'FAILURE', log_details_error)
        return {'error': str(e)}


@shared_task(name='list_iots_task', bind=True)
def list_iots_task(self, user_data, room_pk):
    start_time = time.time()
    user_id = user_data.get('id')
    username = user_data.get('username')
    user_role = user_data.get('tipo_vinculo')
    source_ip = user_data.get('source_ip', 'N/A')
    correlation_id = self.request.id

    log_details_start = f"User: {user_id} ({username}, {user_role}). Source IP: {source_ip}. Resource: room_id={room_pk}."
    log_task(correlation_id, 'INFO', 'list_iots', 'STARTED', log_details_start)
    
    try:
        # A lógica de permissão já está no db-service, aqui só repassamos a chamada.
        # Mas para o log, seria bom ter a checagem de permissão aqui também.
        # Por simplicidade, vamos apenas chamar o serviço por enquanto.
        result_data = call_db_service('iots', params={'room_pk': room_pk})

        if isinstance(result_data, dict) and 'error' in result_data:
            raise Exception(result_data['error'])

        duration = (time.time() - start_time) * 1000
        log_details_end = f"Result: {len(result_data)} IoTs found. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'INFO', 'list_iots', 'SUCCESS', log_details_end)
        
        return result_data

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_details_error = f"Reason: {e}. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'ERROR', 'list_iots', 'FAILURE', log_details_error)
        return {'error': str(e)}