from celery import shared_task
import requests
import time
import json
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
    ensure_user_exists(user_data)

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
    ensure_user_exists(user_data)

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
############################################################################################
def send_mqtt_command(command_data: dict):
    """
    Função auxiliar para enviar um comando para a fila do serviço MQTT.
    Usa o pool de produtores do Celery para enviar uma mensagem bruta,
    compatível com consumidores que não são do Celery (como pika).
    """
    try:
        # Pega um produtor de baixo nível do pool de conexões do Celery
        with celery_app.producer_pool.acquire(block=True) as producer:
            # Serializa nosso dicionário para uma string JSON e a codifica para bytes
            message_body = json.dumps(command_data).encode('utf-8')
            
            # Publica a mensagem diretamente na fila desejada
            producer.publish(
                body=message_body,
                routing_key='mqtt_commands',  # O nome da nossa fila
                content_type='application/json',
                content_encoding='utf-8',
                # Garante que a mensagem seja persistente no RabbitMQ
                delivery_mode=2  
            )
        print(f"Comando MQTT enviado para a fila 'mqtt_commands': {command_data}")
    except Exception as e:
        print(f"ERRO CRÍTICO ao enviar comando para a fila MQTT: {e}")

@shared_task(name='open_door_task', bind=True)
def open_door_task(self, user_data, iot_pk):
    start_time = time.time()
    user_id = user_data.get('id')
    username = user_data.get('username')
    source_ip = user_data.get('source_ip', 'N/A')
    correlation_id = self.request.id

    log_details_start = f"User: {username} ({user_id}). Source IP: {source_ip}. Resource: iot_pk={iot_pk}."
    log_task(correlation_id, 'INFO', 'open_door', 'STARTED', log_details_start)

    try:
        # 1. Obter informações do IOT para saber a sala
        iot_info = call_db_service(f'iots/{iot_pk}')
        if 'error' in iot_info:
            raise Exception(f"IOT com pk={iot_pk} não encontrado.")
        
        room_pk = iot_info.get('room', {}).get('id')
        iot_name = iot_info.get('name')

        # 2. Verificar permissão do usuário para aquela sala
        # Supondo que o db_service possa responder se um usuário tem permissão para uma sala
        permission_info = call_db_service('user-permissions', params={'user': user_id, 'room': room_pk})
        
        if not permission_info: # Se a lista de permissões for vazia
             raise PermissionError(f"Acesso negado: Usuário {username} não tem permissão para a sala {room_pk}.")

        # 3. Se tiver permissão, montar e enviar o comando MQTT
        mqtt_topic = f"campus/geral/{iot_name}/command"
        mqtt_payload = json.dumps({"command": "open", "requested_by": username})
        
        command_to_send = {
            "action": "publish",
            "topic": mqtt_topic,
            "payload": mqtt_payload,
            "qos": 1
        }
        send_mqtt_command(command_to_send)
        
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'INFO', 'open_door', 'SUCCESS', f"Comando 'open' enviado para {iot_name}. Duration: {duration:.2f}ms.")

        return {"status": "success", "message": f"Comando para abrir porta {iot_name} enviado."}

    except PermissionError as e:
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'WARNING', 'open_door', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e), 'status_code': 403} # Retornar um erro de permissão

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        log_task(correlation_id, 'ERROR', 'open_door', 'FAILURE', f"Reason: {e}. Duration: {duration:.2f}ms.")
        return {'error': str(e), 'status_code': 500}