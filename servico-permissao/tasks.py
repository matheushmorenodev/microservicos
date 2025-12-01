import os
import logging
import requests
import time
import json
import asyncio
import uuid
import pika
from celery import Celery
from typing import Callable, Coroutine, Any, Dict, Optional, Tuple

# ==============================================================================
# CONFIGURAÇÃO E AMBIENTE
# ==============================================================================

class ServiceConfig:
    """Centraliza as configurações do serviço."""
    DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://servico-banco-dados:8002/api")
    
    # RabbitMQ (usado para conexão direta RPC via Pika)
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")

# Configuração de Logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Instância do Celery
app = Celery('permission_service')
app.config_from_object('celeryconfig')

# Sessão HTTP Global (Pool de conexões)
try:
    db_session = requests.Session()
    db_session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    logger.info(f"Sessão HTTP inicializada para: {ServiceConfig.DB_SERVICE_URL}")
except Exception as e:
    logger.critical(f"Falha fatal ao criar sessão HTTP: {e}")
    raise e

# ==============================================================================
# GERENCIADOR DE LOGS (LOGGING MANAGER)
# ==============================================================================

class LoggingManager:
    """
    Gerenciador de logs híbrido (Console + Serviço Centralizado via Celery).
    """
    def __init__(self, service_name: str, logger_instance: logging.Logger, log_sender_func: Callable):
        self.service_name = service_name
        self.logger = logger_instance
        self.log_sender_func = log_sender_func
        self.is_async = asyncio.iscoroutinefunction(log_sender_func)

    def _log_local(self, level: str, message: str, exc_info: bool = False):
        method = getattr(self.logger, level.lower(), self.logger.debug)
        method(message, exc_info=exc_info)

    def _send_remote(self, level: str, message: str, cid: str):
        try:
            result = self.log_sender_func(self.service_name, level, message, cid)
            if self.is_async and isinstance(result, Coroutine):
                asyncio.create_task(result)
        except Exception as e:
            self.logger.error(f"[CID: {cid}] Falha ao enviar log remoto: {e}", exc_info=True)

    def _process(self, level: str, action: str, user: str, status: str, details: str, cid: str, exc_info: bool):
        details_str = f". {details.strip()}" if details else ""
        
        # Formatos de mensagem
        db_msg = f"User: {user}, Action: {action}, Status: {status}{details_str}"
        console_msg = f"[CID: {cid}] {db_msg}"
        
        self._log_local(level, console_msg, exc_info)
        self._send_remote(level, db_msg, cid)

    def info(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A"):
        self._process('INFO', action, user, status, details, cid, False)

    def warning(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A"):
        self._process('WARNING', action, user, status, details, cid, False)

    def error(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A", exc_info: bool = True):
        self._process('ERROR', action, user, status, details, cid, exc_info)

def _send_log_to_celery_task(service_name: str, level: str, message: str, cid: str):
    """Envia a tarefa de log para a fila do Celery."""
    app.send_task(
        'save_log_task',
        args=[service_name, level, message, cid],
        queue='log_queue',
        retry=False
    )

log_manager = LoggingManager("permission_service", logger, _send_log_to_celery_task)

# ==============================================================================
# HELPERS DE COMUNICAÇÃO (DB & RABBITMQ)
# ==============================================================================

def call_db_service(endpoint: str, params: Dict = None, cid: str = "N/A") -> Any:
    """Realiza chamada GET ao serviço de banco de dados."""
    url = f"{ServiceConfig.DB_SERVICE_URL}/{endpoint}/"
    try:
        response = db_session.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"[CID: {cid}] Erro DB Service ({url}): {e}")
        raise e

def ensure_user_exists(user_data: Dict, cid: str = "N/A"):
    """Garante que o usuário exista no DB Service para integridade referencial."""
    user_id = user_data.get('id')
    username = user_data.get('username', 'unknown')
    
    if not user_id: 
        return

    payload = {
        'user_id': user_id,
        'username': username,
        'role': user_data.get('tipo_vinculo', 'Aluno')
    }
    
    try:
        url = f"{ServiceConfig.DB_SERVICE_URL}/users/{user_id}/"
        resp = db_session.put(url, json=payload, timeout=5)
        resp.raise_for_status()
        log_manager.info("ensure_user_exists", username, "SUCCESS", f"Synced user {user_id}", cid)
    except Exception as e:
        log_manager.warning("ensure_user_exists", username, "FAILURE", str(e), cid)

def send_door_command_async(command_data: Dict, user: str, cid: str):
    """Fire-and-forget: Envia comando para o door_service sem esperar resposta."""
    try:
        app.send_task('process_command', args=[command_data], queue='door_commands')
        log_manager.info("send_command_async", user, "SUCCESS", f"Action: {command_data.get('action')}", cid)
    except Exception as e:
        log_manager.error("send_command_async", user, "FAILURE", str(e), cid)
        raise e

def send_door_command_rpc(command_data: Dict, cid: str = None) -> Dict:
    """
    RPC Síncrono: Envia comando via Pika e bloqueia aguardando resposta na fila temporária.
    """
    credentials = pika.PlainCredentials(ServiceConfig.RABBITMQ_USER, ServiceConfig.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=ServiceConfig.RABBITMQ_HOST, 
        port=ServiceConfig.RABBITMQ_PORT, 
        credentials=credentials
    )
    
    connection = None
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Fila temporária para resposta
        result = channel.queue_declare(queue='', exclusive=True)
        callback_queue = result.method.queue
        
        correlation_id = cid or str(uuid.uuid4())
        response = None

        def on_response(ch, method, props, body):
            nonlocal response
            if props.correlation_id == correlation_id:
                response = json.loads(body)

        channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

        channel.basic_publish(
            exchange='',
            routing_key='door_commands',
            properties=pika.BasicProperties(reply_to=callback_queue, correlation_id=correlation_id),
            body=json.dumps(command_data)
        )

        # Polling com timeout (5 segundos)
        start_time = time.time()
        while response is None:
            connection.process_data_events(time_limit=1)
            if time.time() - start_time > 5:
                raise TimeoutError("BridgeService RPC Timeout")
        
        return response

    except Exception as e:
        raise e
    finally:
        if connection and not connection.is_closed:
            connection.close()

# ==============================================================================
# LÓGICA DE NEGÓCIO COMPARTILHADA (HELPER)
# ==============================================================================

def _get_iot_context_and_verify_access(user_data: Dict, iot_pk: int, action_name: str, cid: str) -> Tuple[Dict, str, str]:
    """
    1. Busca dados do IoT.
    2. Valida integridade dos dados (Depto, Sala).
    3. Verifica se IoT está Online.
    4. Verifica permissões do usuário (Se não for Servidor).
    
    Retorna: (iot_info_dict, iot_name, mqtt_topic_suffix)
    """
    username = user_data.get('username', 'unknown')
    user_type = user_data.get('tipo_vinculo')
    user_id = user_data.get('id')

    # 1. Buscar Dados
    iot_info = call_db_service(f'iots/{iot_pk}', cid=cid)
    if not iot_info or not isinstance(iot_info, dict):
        raise ValueError(f"IoT {iot_pk} não encontrado ou resposta inválida.")

    # 2. Extração e Validação
    iot_name = iot_info.get('name')
    iot_status = iot_info.get('status')
    room_info = iot_info.get('room', {})
    room_pk = room_info.get('id')
    room_name = room_info.get('name')
    dept_name = room_info.get('department', {}).get('name')

    missing_fields = [k for k, v in {
        'iot_name': iot_name, 'room_pk': room_pk, 
        'room_name': room_name, 'dept': dept_name
    }.items() if v is None]

    if missing_fields:
        raise ValueError(f"Dados incompletos do IoT {iot_pk}: {missing_fields}")

    log_manager.info(action_name, username, "DATA_VALIDATED", f"IoT: {iot_name}, Sala: {room_name}", cid)

    # 3. Check Online (Necessário para operar e ver status em tempo real)
    if iot_status is not True:
        raise PermissionError(f"IoT '{iot_name}' está OFFLINE.")

    # 4. Check Permissões
    if user_type != 'Servidor':
        log_manager.info(action_name, username, "CHECKING_PERMS", f"Verificando acesso sala {room_pk}", cid)
        perms = call_db_service('user-permissions', params={'user': user_id, 'room': room_pk}, cid=cid)
        if not perms:
            raise PermissionError(f"Acesso negado à sala {room_pk}.")
    else:
        log_manager.info(action_name, username, "BYPASSING_PERMS", "Acesso Servidor", cid)

    # Constrói a base do tópico: "Departamento/Sala/IoT"
    # O chamador decide se adiciona "/comando" ou "/status"
    topic_base = f"{dept_name}/{room_name}/{iot_name}"
    
    return iot_info, iot_name, topic_base

# ==============================================================================
# TASKS CELERY
# ==============================================================================

@app.task(name='list_departments_task', bind=True, autoretry_for=(Exception,), max_retries=3)
def list_departments_task(self, user_data):
    cid = self.request.id
    username = user_data.get('username')
    ensure_user_exists(user_data, cid)
    
    log_manager.info("list_departments", username, "STARTED", cid=cid)
    try:
        params = {}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        result = call_db_service('departments', params=params, cid=cid)
        log_manager.info("list_departments", username, "SUCCESS", f"Count: {len(result)}", cid)
        return {'result': result}
    except Exception as e:
        log_manager.error("list_departments", username, "FAILURE", str(e), cid)
        return {'error': str(e), 'status_code': 500}

@app.task(name='list_rooms_task', bind=True, autoretry_for=(Exception,), max_retries=3)
def list_rooms_task(self, user_data, department_pk):
    cid = self.request.id
    username = user_data.get('username')
    
    log_manager.info("list_rooms", username, "STARTED", f"Dept: {department_pk}", cid)
    try:
        params = {'department_pk': department_pk}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        result = call_db_service('rooms', params=params, cid=cid)
        log_manager.info("list_rooms", username, "SUCCESS", f"Count: {len(result)}", cid)
        return {'result': result}
    except Exception as e:
        log_manager.error("list_rooms", username, "FAILURE", str(e), cid)
        return {'error': str(e), 'status_code': 500}

@app.task(name='list_iots_task', bind=True, autoretry_for=(Exception,), max_retries=3)
def list_iots_task(self, user_data, room_pk):
    cid = self.request.id
    username = user_data.get('username')
    user_type = user_data.get('tipo_vinculo')
    
    log_manager.info("list_iots", username, "STARTED", f"Room: {room_pk}", cid)
    try:
        params = {'room_pk': room_pk}
        if user_type != 'Servidor':
            params['user_id'] = user_data.get('id')
            params['status'] = 'true' # Alunos só veem online
        
        result = call_db_service('iots', params=params, cid=cid)
        log_manager.info("list_iots", username, "SUCCESS", f"Count: {len(result)}", cid)
        return {'result': result}
    except Exception as e:
        log_manager.error("list_iots", username, "FAILURE", str(e), cid)
        return {'error': str(e), 'status_code': 500}

@app.task(name='open_door_task', bind=True, autoretry_for=(Exception,), max_retries=3)
def open_door_task(self, user_data, iot_pk):
    cid = self.request.id
    username = user_data.get('username')
    
    log_manager.info("open_door", username, "STARTED", f"IoT: {iot_pk}", cid)
    try:
        # Usa o helper para validar e obter dados
        _, iot_name, topic_base = _get_iot_context_and_verify_access(user_data, iot_pk, "open_door", cid)
        
        command_topic = f"{topic_base}/comando"
        
        payload = {
            "action": "publish",
            "topic": command_topic,
            "payload": json.dumps({"command": "open", "requested_by": username}),
            "qos": 1, "retain": False
        }
        
        send_door_command_async(payload, username, cid)
        
        log_manager.info("open_door", username, "SUCCESS", f"Sent to {command_topic}", cid)
        return {"status": "success", "message": f"Comando enviado para {iot_name}"}

    except PermissionError as e:
        log_manager.warning("open_door", username, "FORBIDDEN", str(e), cid)
        return {'error': str(e), 'status_code': 403}
    except Exception as e:
        log_manager.error("open_door", username, "sys_error", str(e), cid)
        return {'error': str(e), 'status_code': 500}

@app.task(name='get_door_status_task', bind=True, autoretry_for=(Exception,), max_retries=3)
def get_door_status_task(self, user_data, iot_pk):
    cid = self.request.id
    username = user_data.get('username')
    
    log_manager.info("get_status", username, "STARTED", f"IoT: {iot_pk}", cid)
    try:
        # Usa o helper para validar e obter dados (Reutilização de código!)
        _, iot_name, topic_base = _get_iot_context_and_verify_access(user_data, iot_pk, "get_status", cid)
        
        status_topic = f"{topic_base}/status"
        
        # Chamada RPC Síncrona
        payload = {"action": "status", "topic": status_topic}
        response = send_door_command_rpc(payload, cid)
        
        if response.get('status') == 'error':
            raise Exception(f"Bridge Error: {response.get('error')}")
            
        iot_state = response.get('data')
        
        log_manager.info("get_status", username, "SUCCESS", f"State: {iot_state}", cid)
        return {
            "status": "success",
            "iot_pk": iot_pk,
            "iot_name": iot_name,
            "last_state": iot_state
        }

    except PermissionError as e:
        log_manager.warning("get_status", username, "FORBIDDEN", str(e), cid)
        return {'error': str(e), 'status_code': 403}
    except Exception as e:
        log_manager.error("get_status", username, "sys_error", str(e), cid)
        return {'error': str(e), 'status_code': 500}