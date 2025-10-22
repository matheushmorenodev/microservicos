import os
import logging
import requests
import time
import json
from celery import Celery

# =======================================================================================================================
#                                 Configuração
# =======================================================================================================================
# Configuração de logging padrão
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cria a instância do Celery específica para este serviço
app = Celery('permission_service')

# Carrega a configuração do arquivo celeryconfig.py
app.config_from_object('celeryconfig')

# URL do serviço de banco de dados (o nome 'db-service' vem do Docker Compose)
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://db-service:8002/api")


# =======================================================================================================================
#                         Funções auxiliares para comunicação com o serviço de banco de dados
# =======================================================================================================================

def ensure_user_exists(user_data):
    """
    Sincroniza dados do usuário com o db-service.
    Falhas aqui são registradas, mas não param a tarefa principal.
    """
    user_id = user_data.get('id')
    if not user_id:
        return
    
    data_to_sync = {
        'user_id': user_id,
        'username': user_data.get('username'),
        'role': user_data.get('tipo_vinculo', 'Aluno')
    }
    try:
        requests.put(f"{DB_SERVICE_URL}/users/{user_id}/", json=data_to_sync, timeout=5)
        logger.info(f"Usuário {user_id} sincronizado.")
    except requests.RequestException as e:
        # Esta é uma operação "fire-and-forget", então apenas registramos o aviso
        logger.warning(f"AVISO: Falha ao sincronizar usuário {user_id}: {e}")

def call_db_service(endpoint, params=None):
    """
    Faz chamadas GET ao db-service.
    Lança uma exceção em caso de erro, permitindo que o Celery tente novamente.
    """
    try:
        response = requests.get(f"{DB_SERVICE_URL}/{endpoint}/", params=params, timeout=5)
        response.raise_for_status() # Lança exceção para erros HTTP (4xx, 5xx)
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Erro de comunicação com db-service em {endpoint}: {e}")
        # Relança a exceção para que o 'autoretry_for' da tarefa funcione
        raise e

# =======================================================================================================================
#                                Funções de envio de tarefas para outros workers
# =======================================================================================================================

def log_task(correlation_id, level, action, status, details=""):
    """Envia uma tarefa para a fila de logs."""
    try:
        log_message = f"Action: {action}. Status: {status}. {details}"
        app.send_task(
            'save_log_task',
            args=['permission-worker', level, log_message, correlation_id],
            queue='log_queue'
        )
    except Exception as e:
        # Se o logging falhar, não queremos que a tarefa principal falhe
        logger.error(f"CRÍTICO: Falha ao enviar log para log_service: {e}")

# =======================================================================================================================
#                               Função para enviar comandos MQTT via fila RabbitMQ
# =======================================================================================================================
def send_door_command(command_data: dict):
    """
    Envia um comando para o worker 'door_service' através da fila 'door_commands'.
    """
    try:
        app.send_task(
            'process_command',
            args=[command_data],
            queue='door_commands'
        )
        logger.info(f"Comando enviado para 'door_commands': {command_data.get('action')} em {command_data.get('topic')}")
    except Exception as e:
        logger.exception(f"ERRO CRÍTICO ao enviar comando para a fila 'door_commands': {e}")
        # Relançar a exceção pode ser necessário se for vital que o comando seja enviado
        raise e

# =======================================================================================================================
#                                              Tarefas Celery
# =======================================================================================================================
@app.task(
    name='list_departments_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_departments_task(self, user_data):
    start_time = time.time()
    correlation_id = self.request.id
    ensure_user_exists(user_data)
    log_task(correlation_id, 'INFO', 'list_departments', 'STARTED', f"User: {user_data.get('username')}")
    
    try:
        if user_data.get('tipo_vinculo') == 'Servidor':
            result = call_db_service('departments')
        else:
            result = call_db_service('departments', params={'user_id': user_data.get('id')})
        
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'INFO', 'list_departments', 'SUCCESS', f"Result: {len(result)} depts. Duration: {duration:.2f}ms.")
        return result
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'ERROR', 'list_departments', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e)}

@app.task(
    name='list_rooms_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_rooms_task(self, user_data, department_pk):
    start_time = time.time()
    correlation_id = self.request.id
    log_details_start = f"User: {user_data.get('username')}. Dept: {department_pk}."
    log_task(correlation_id, 'INFO', 'list_rooms', 'STARTED', log_details_start)

    try:
        params = {'department_pk': department_pk}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        result_data = call_db_service('rooms', params=params)
        
        duration = (time.time() - start_time) * 1000
        log_details_end = f"Result: {len(result_data)} rooms. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'INFO', 'list_rooms', 'SUCCESS', log_details_end)
        return result_data
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'ERROR', 'list_rooms', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e)}

@app.task(
    name='list_iots_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_iots_task(self, user_data, room_pk):
    start_time = time.time()
    correlation_id = self.request.id
    log_details_start = f"User: {user_data.get('username')}. Room: {room_pk}."
    log_task(correlation_id, 'INFO', 'list_iots', 'STARTED', log_details_start)
    
    try:
        params = {'room_pk': room_pk, 'user_id': user_data.get('id')}
        result_data = call_db_service('iots', params=params)

        duration = (time.time() - start_time) * 1000
        log_details_end = f"Result: {len(result_data)} IoTs. Duration: {duration:.2f}ms."
        log_task(correlation_id, 'INFO', 'list_iots', 'SUCCESS', log_details_end)
        return result_data
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'ERROR', 'list_iots', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e)}

@app.task(
    name='open_door_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def open_door_task(self, user_data, iot_pk):
    start_time = time.time()
    correlation_id = self.request.id
    username = user_data.get('username')
    log_task(correlation_id, 'INFO', 'open_door', 'STARTED', f"User: {username}, IoT: {iot_pk}.")
    
    try:
        # 1. Obter informações do IoT (e implicitamente da sala)
        iot_info = call_db_service(f'iots/{iot_pk}')
        room_pk = iot_info.get('room', {}).get('id')
        iot_name = iot_info.get('name')
        
        if not room_pk or not iot_name:
             raise Exception(f"Informações incompletas para IOT com pk={iot_pk}.")

        # 2. Verificar permissão do usuário para a sala
        permission_info = call_db_service('user-permissions', params={'user': user_data.get('id'), 'room': room_pk})
        if not permission_info:
            # Isso não é um erro do sistema, é uma falha de permissão
            raise PermissionError(f"Acesso negado: Usuário {username} não tem permissão para a sala {room_pk}.")

        # 3. Se tudo estiver OK, enviar o comando para o door_service
        command_to_send = {
            "action": "publish",
            "topic": f"campus/geral/{iot_name}/command",
            "payload": json.dumps({"command": "open", "requested_by": username}),
            "qos": 1,
            "retain": False
        }
        
        # Use a nova função de envio de tarefa
        send_door_command(command_to_send)
        
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'INFO', 'open_door', 'SUCCESS', f"Comando 'open' enviado para {iot_name}. Duration: {duration:.2f}ms.")
        return {"status": "success", "message": f"Comando para abrir porta {iot_name} enviado."}
    
    except PermissionError as e: # Erro de negócio (403)
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'WARNING', 'open_door', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e), 'status_code': 403}
        
    except Exception as e: # Erro de sistema (500)
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'ERROR', 'open_door', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        # 'e' pode ser uma RequestException que o autoretry não conseguiu resolver
        return {'error': str(e), 'status_code': 500}