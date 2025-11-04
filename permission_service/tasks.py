import os
import logging
import requests
import time
import json
import asyncio
from celery import Celery
from requests.sessions import Session
from typing import Callable, Coroutine, Any

# =======================================================================================================================
#                               Configuração
# =======================================================================================================================

# 1. Configuração de logging profissional para o terminal
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# 2. Cria a instância do Celery
app = Celery('permission_service')
app.config_from_object('celeryconfig')

# 3. URL do serviço de banco de dados
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://db-service:8002/api")

# 4. Pool de Conexões HTTP (Performance)
try:
    db_session = requests.Session()
    db_session.headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    })
    logger.info(f"Sessão HTTP para o db-service ({DB_SERVICE_URL}) inicializada.")
except Exception as e:
    logger.critical(f"Falha ao criar sessão HTTP: {e}")
    raise e

# =======================================================================================================================
#                               PADRÃO DE LOG CENTRALIZADO
# =======================================================================================================================

class LoggingManager:
    """
    Gerenciador de log padronizado para microsserviços.
    Envia logs para o console local e para um serviço de log centralizado
    de forma síncrona ou assíncrona.
    """
    def __init__(self, service_name: str, logger: logging.Logger, log_sender_func: Callable):
        self.service_name = service_name
        self.logger = logger
        self.log_sender_func = log_sender_func
        self.is_async = asyncio.iscoroutinefunction(log_sender_func)

    def _log_to_console(self, level: str, message: str, exc_info: bool = False):
        """Loga a mensagem formatada no console local."""
        if level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message, exc_info=exc_info)
        elif level == 'CRITICAL':
            self.logger.critical(message, exc_info=exc_info)
        else:
            self.logger.debug(message)

    def _send_to_log_service(self, level: str, message: str, cid: str):
        """Envia o log para o serviço centralizado usando a função injetada."""
        try:
            result = self.log_sender_func(
                service_name=self.service_name,
                level=level,
                message=message,
                cid=cid
            )
            if self.is_async and isinstance(result, Coroutine):
                asyncio.create_task(result)
                
        except Exception as e:
            self.logger.error(f"[CID: {cid}] CRÍTICO: Falha ao enviar log para log_service: {e}", exc_info=True)

    # --- Métodos Públicos (MUDANÇA DE PADRÃO) ---
    # Agora forçamos os argumentos 'action' e 'user' para padronização

    def _build_messages(self, action: str, user: str, status: str, details: str, cid: str):
        """Helper para construir as mensagens de log de forma padronizada."""
        # Remove detalhes vazios para um log mais limpo
        details_str = f". {details.strip()}" if details else ""
        
        # Mensagem para o DB (sem CID, pois é um campo separado)
        db_msg = f"User: {user}, Action: {action}, Status: {status}{details_str}"
        
        # Mensagem para o Console (com CID)
        console_msg = f"[CID: {cid}] {db_msg}"
        
        return console_msg, db_msg

    def info(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A"):
        """Loga em nível INFO no console e no serviço de log."""
        console_msg, db_msg = self._build_messages(action, user, status, details, cid)
        self._log_to_console('INFO', console_msg)
        self._send_to_log_service('INFO', db_msg, cid)

    def warning(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A"):
        """Loga em nível WARNING no console e no serviço de log."""
        console_msg, db_msg = self._build_messages(action, user, status, details, cid)
        self._log_to_console('WARNING', console_msg)
        self._send_to_log_service('WARNING', db_msg, cid)

    def error(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A", exc_info: bool = True):
        """Loga em nível ERROR no console e no serviço de log."""
        console_msg, db_msg = self._build_messages(action, user, status, details, cid)
        # exc_info=True garante que o stack trace apareça no console
        self._log_to_console('ERROR', console_msg, exc_info=exc_info)
        self._send_to_log_service('ERROR', db_msg, cid)

    def critical(self, action: str, user: str, status: str, details: str = "", cid: str = "N/A", exc_info: bool = True):
        """Loga em nível CRITICAL no console e no serviço de log."""
        console_msg, db_msg = self._build_messages(action, user, status, details, cid)
        self._log_to_console('CRITICAL', console_msg, exc_info=exc_info)
        self._send_to_log_service('CRITICAL', message, cid)


# -----------------------------------------------------------------------------------------------------------------------
# Instanciação do Padrão de Log
# -----------------------------------------------------------------------------------------------------------------------

def _send_log_to_celery(service_name: str, level: str, message: str, cid: str):
    """Função "sender" SÍNCRONA para o Celery."""
    try:
        app.send_task(
            'save_log_task',
            args=[service_name, level, message, cid],
            queue='log_queue',
            retry=False
        )
    except Exception as e:
        raise e

# --- Instância Global do Gerenciador de Log ---
log_manager = LoggingManager(
    service_name="permission_service", # <-- CORRIGIDO
    logger=logger,
    log_sender_func=_send_log_to_celery
)

# =======================================================================================================================
#                               Funções auxiliares
# =======================================================================================================================

def ensure_user_exists(user_data, cid="N/A"):
    """Sincroniza dados do usuário com o db-service."""
    user_id = user_data.get('id')
    username = user_data.get('username', 'unknown')
    if not user_id:
        return
    
    data_to_sync = {
        'user_id': user_id,
        'username': username,
        'role': user_data.get('tipo_vinculo', 'Aluno')
    }
    try:
        response = db_session.put(f"{DB_SERVICE_URL}/users/{user_id}/", json=data_to_sync, timeout=5)
        response.raise_for_status()
        log_manager.info(
            action="ensure_user_exists", 
            user=username, 
            status="SUCCESS", 
            details=f"User {user_id} synced.", 
            cid=cid
        )
    except requests.RequestException as e:
        log_manager.warning(
            action="ensure_user_exists", 
            user=username, 
            status="FAILURE", 
            details=f"Falha ao sincronizar usuário {user_id}: {e}", 
            cid=cid
        )

def call_db_service(endpoint, params=None, cid="N/A"):
    """Faz chamadas GET ao db-service usando a sessão global."""
    try:
        response = db_session.get(f"{DB_SERVICE_URL}/{endpoint}/", params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"[CID: {cid}] Erro de comunicação com db-service em {endpoint}: {e}")
        raise e

def send_door_command(command_data: dict, user: str = "system", cid: str = "N/A"):
    """Envia um comando para o worker 'door_service'."""
    try:
        app.send_task(
            'process_command',
            args=[command_data],
            queue='door_commands'
        )
        log_manager.info(
            action="send_door_command", 
            user=user, 
            status="SUCCESS", 
            details=f"Action: {command_data.get('action')} to topic: {command_data.get('topic')}", 
            cid=cid
        )
    except Exception as e:
        log_manager.error(
            action="send_door_command", 
            user=user, 
            status="FAILURE", 
            details=f"Erro ao enviar para fila 'door_commands': {e}", 
            cid=cid
        )
        raise e

# =======================================================================================================================
#                               Tarefas Celery (Logs Simplificados)
# =======================================================================================================================

@app.task(
    name='list_departments_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_departments_task(self, user_data):
    correlation_id = self.request.id
    username = user_data.get('username', 'unknown')
    ensure_user_exists(user_data, cid=correlation_id)
    
    log_manager.info(
        action="list_departments", 
        user=username, 
        status="STARTED", 
        cid=correlation_id
    )
    
    try:
        if user_data.get('tipo_vinculo') == 'Servidor':
            result = call_db_service('departments', cid=correlation_id)
        else:
            result = call_db_service('departments', params={'user_id': user_data.get('id')}, cid=correlation_id)
        
        log_manager.info(
            action="list_departments", 
            user=username, 
            status="SUCCESS", 
            details=f"Result: {len(result)} depts.", 
            cid=correlation_id
        )
        return {'result': result}
    except Exception as e:
        log_manager.error(
            action="list_departments", 
            user=username, 
            status="FAILURE", 
            details=f"Reason: {e}", 
            cid=correlation_id
        )
        return {'error': str(e), 'status_code': 500}

@app.task(
    name='list_rooms_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_rooms_task(self, user_data, department_pk):
    correlation_id = self.request.id
    username = user_data.get('username', 'unknown')
    
    log_manager.info(
        action="list_rooms", 
        user=username, 
        status="STARTED", 
        details=f"Dept: {department_pk}", 
        cid=correlation_id
    )

    try:
        params = {'department_pk': department_pk}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        result_data = call_db_service('rooms', params=params, cid=correlation_id)
        
        log_manager.info(
            action="list_rooms", 
            user=username, 
            status="SUCCESS", 
            details=f"Dept: {department_pk}, Result: {len(result_data)} rooms.", 
            cid=correlation_id
        )
        return {'result': result_data}
    except Exception as e:
        log_manager.error(
            action="list_rooms", 
            user=username, 
            status="FAILURE", 
            details=f"Dept: {department_pk}, Reason: {e}", 
            cid=correlation_id
        )
        return {'error': str(e), 'status_code': 500}

@app.task(
    name='list_iots_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def list_iots_task(self, user_data, room_pk):
    correlation_id = self.request.id
    username = user_data.get('username', 'unknown')
    user_type = user_data.get('tipo_vinculo', 'Aluno')
    
    log_manager.info(
        action="list_iots", 
        user=username, 
        status="STARTED", 
        details=f"UserType: {user_type}, Room: {room_pk}", 
        cid=correlation_id
    )
    
    try:
        # 1. Parâmetro base: sempre filtramos pela sala
        params = {'room_pk': room_pk}

        # 2. Lógica condicional baseada no tipo de usuário
        if user_type == 'Servidor':
            # Servidores veem todos os IoTs (ativos ou inativos) da sala.
            pass # Nenhum outro parâmetro é necessário
        
        else:
            # Alunos (ou outros) veem apenas IoTs ATIVOS e que eles TÊM PERMISSÃO
            params['user_id'] = user_data.get('id')
            params['status'] = 'true' # Filtro de status
        
        # 3. Chama o db-service com os parâmetros definidos
        result_data = call_db_service('iots', params=params, cid=correlation_id)

        log_manager.info(
            action="list_iots", 
            user=username, 
            status="SUCCESS", 
            details=f"Room: {room_pk}, Result: {len(result_data)} IoTs.", 
            cid=correlation_id
        )
        return {'result': result_data}
    
    except Exception as e:
        log_manager.error(
            action="list_iots", 
            user=username, 
            status="FAILURE", 
            details=f"Room: {room_pk}, Reason: {e}", 
            cid=correlation_id
        )
        return {'error': str(e), 'status_code': 500}


@app.task(
    name='open_door_task', 
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    max_retries=3
)
def open_door_task(self, user_data, iot_pk):
    correlation_id = self.request.id
    username = user_data.get('username', 'unknown')
    
    log_manager.info(
        action="open_door", 
        user=username, 
        status="STARTED", 
        details=f"IoT: {iot_pk}", 
        cid=correlation_id
    )
    
    try:
        # 1. Obter informações do IoT
        iot_info = call_db_service(f'iots/{iot_pk}', cid=correlation_id)
        room_pk = iot_info.get('room', {}).get('id')
        iot_name = iot_info.get('name')
        command_topic = iot_info.get('command_topic')

        if not all([room_pk, iot_name, command_topic]):
            missing = [k for k in ['room_pk', 'iot_name', 'command_topic'] if not locals().get(k)]
            details = f"Dados incompletos do db-service para IOT {iot_pk}. Faltando: {missing}"
            log_manager.error(action="open_door", user=username, status="FAILURE", details=details, cid=correlation_id)
            raise Exception(details)

        # 2. Verificar permissão
        params = {'user': user_data.get('id'), 'room': room_pk}
        permission_info = call_db_service('user-permissions', params=params, cid=correlation_id)
        
        if not permission_info:
            raise PermissionError(f"Acesso negado: Usuário não tem permissão para a sala {room_pk}.")

        # 3. Enviar o comando
        command_to_send = {
            "action": "publish",
            "topic": command_topic,
            "payload": json.dumps({"command": "open", "requested_by": username}),
            "qos": 1,
            "retain": False
        }
        
        send_door_command(command_to_send, user=username, cid=correlation_id)
        
        log_manager.info(
            action="open_door", 
            user=username, 
            status="SUCCESS", 
            details=f"Comando 'open' enviado para {iot_name} (Tópico: {command_topic}).", 
            cid=correlation_id
        )
        return {"status": "success", "message": f"Comando para abrir porta {iot_name} enviado."}
    
    except PermissionError as e: # Erro de negócio (403)
        log_manager.warning(
            action="open_door", 
            user=username, 
            status="FAILURE", 
            details=f"Reason: {e}", 
            cid=correlation_id
        )
        return {'error': str(e), 'status_code': 403}
        
    except Exception as e: # Erro de sistema (500)
        log_manager.error(
            action="open_door", 
            user=username, 
            status="FAILURE", 
            details=f"Reason: {e}", 
            cid=correlation_id
        )
        return {'error': str(e), 'status_code': 500}