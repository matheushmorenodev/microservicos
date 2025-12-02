import os
import logging
import requests
import json
import uuid
import time
import pika
from celery import Celery, Task

# ==============================================================================
# 1. CONFIGURAÇÃO
# ==============================================================================

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://servico-banco-dados:8002/api")

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBIT_USER = os.getenv("RABBITMQ_USER", "guest")
RABBIT_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBIT_PORT = int(os.getenv("RABBITMQ_PORT", 5672))

app = Celery('permission_service')
app.config_from_object('celeryconfig')

# ==============================================================================
# 2. LOGGING CONTEXTUAL
# ==============================================================================

class ContextLogger:
    def __init__(self, service_name, correlation_id, user_identifier):
        self.service = service_name
        self.cid = correlation_id
        self.user = user_identifier or "ANONYMOUS"
        self.local_logger = logging.getLogger(service_name)

    def _log(self, level, msg):
        full_msg = f"[{self.cid}] [User: {self.user}] {msg}"
        if level == 'info': self.local_logger.info(full_msg)
        elif level == 'error': self.local_logger.error(full_msg)
        elif level == 'warning': self.local_logger.warning(full_msg)

        try:
            app.send_task(
                'save_log_task',
                args=[self.service, level.upper(), full_msg, self.cid],
                queue='log_queue'
            )
        except Exception:
            pass

    def info(self, msg): self._log('info', msg)
    def error(self, msg): self._log('error', msg)
    def warning(self, msg): self._log('warning', msg)

class StandardTask(Task):
    def __call__(self, *args, **kwargs):
        req = self.request
        cid = getattr(req, 'correlation_id', None) 
        if not cid and 'correlation_id' in kwargs:
            cid = kwargs['correlation_id']
        if not cid:
            cid = 'UNKNOWN-CID'

        user_id = "SYSTEM"
        if args and isinstance(args[0], dict):
            user_id = args[0].get('username') or args[0].get('matricula') or args[0].get('id') or "UNKNOWN"
        
        self.logger = ContextLogger("ServicoPermissao", cid, user_id)
        self.cid = cid
        self.current_user = user_id
        
        return super().__call__(*args, **kwargs)

# ==============================================================================
# 3. HELPER RPC
# ==============================================================================
def rpc_call_bridge(payload, correlation_id):
    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    parameters = pika.ConnectionParameters(host=RABBIT_HOST, port=RABBIT_PORT, credentials=credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    result = channel.queue_declare(queue='', exclusive=True)
    callback_queue = result.method.queue
    response = None

    def on_response(ch, method, props, body):
        nonlocal response
        if props.correlation_id == correlation_id:
            response = json.loads(body)

    channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

    channel.basic_publish(
        exchange='',
        routing_key='door_commands',
        properties=pika.BasicProperties(
            reply_to=callback_queue,
            correlation_id=correlation_id,
            content_type='application/json'
        ),
        body=json.dumps(payload)
    )

    start_time = time.time()
    while response is None:
        connection.process_data_events()
        if time.time() - start_time > 5:
            connection.close()
            raise TimeoutError("Bridge Service não respondeu.")

    connection.close()
    return response

# ==============================================================================
# 4. TAREFAS DE NEGÓCIO (COM LOGS ENRIQUECIDOS)
# ==============================================================================

@app.task(base=StandardTask, bind=True, name='list_departments_task')
def list_departments_task(self, user_data):
    self.logger.info("Iniciando listagem de departamentos.")
    try:
        headers = {'X-Correlation-ID': self.cid}
        params = {}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        resp = requests.get(f"{DB_SERVICE_URL}/departments/", params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        self.logger.info(f"Listagem concluída. {len(data)} departamentos encontrados.")
        return {'result': data}
    except Exception as e:
        self.logger.error(f"Erro ao listar departamentos: {e}")
        return {'error': str(e)}

@app.task(base=StandardTask, bind=True, name='list_rooms_task')
def list_rooms_task(self, user_data, department_pk):
    # 1. Busca prévia do nome do Departamento para o log
    headers = {'X-Correlation-ID': self.cid}
    dept_name = "Desconhecido"
    try:
        # Consulta rápida ao detalhe do departamento
        dept_info = requests.get(f"{DB_SERVICE_URL}/departments/{department_pk}/", headers=headers, timeout=3).json()
        dept_name = dept_info.get('name', 'Desconhecido')
    except:
        pass # Se falhar, loga como desconhecido mas continua o fluxo

    # LOG RICO COMO SOLICITADO
    self.logger.info(f"Buscando salas do Departamento '{dept_name}' #ID {department_pk}.")

    try:
        params = {'department_pk': department_pk}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            
        resp = requests.get(f"{DB_SERVICE_URL}/rooms/", params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        self.logger.info(f"Encontradas {len(data)} salas em '{dept_name}'.")
        return {'result': data}
    except Exception as e:
        self.logger.error(f"Erro ao listar salas: {e}")
        return {'error': str(e)}

@app.task(base=StandardTask, bind=True, name='list_iots_task')
def list_iots_task(self, user_data, room_pk):
    # 1. Busca prévia do nome da Sala para o log
    headers = {'X-Correlation-ID': self.cid}
    room_name = "Desconhecida"
    try:
        room_info = requests.get(f"{DB_SERVICE_URL}/rooms/{room_pk}/", headers=headers, timeout=3).json()
        room_name = room_info.get('name', 'Desconhecida')
    except:
        pass

    # LOG RICO COMO SOLICITADO
    self.logger.info(f"Buscando IoTs da Sala '{room_name}' #ID {room_pk}.")

    try:
        params = {'room_pk': room_pk}
        if user_data.get('tipo_vinculo') != 'Servidor':
            params['user_id'] = user_data.get('id')
            params['status'] = 'true'
            
        resp = requests.get(f"{DB_SERVICE_URL}/iots/", params=params, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        self.logger.info(f"Retornando {len(data)} IoTs da sala '{room_name}'.")
        return {'result': data}
    except Exception as e:
        self.logger.error(f"Erro ao listar IoTs: {e}")
        return {'error': str(e)}

@app.task(base=StandardTask, bind=True, name='open_door_task')
def open_door_task(self, user_data, iot_pk):
    # O Log inicial já será feito de forma rica após buscar os dados abaixo
    try:
        headers = {'X-Correlation-ID': self.cid}
        
        # 1. Busca dados completos
        resp_iot = requests.get(f"{DB_SERVICE_URL}/iots/{iot_pk}/", headers=headers, timeout=5)
        if resp_iot.status_code != 200: raise Exception("IoT não encontrado")
        iot_data = resp_iot.json()
        
        iot_name = iot_data['name']
        room_name = iot_data['room']['name']
        dept_name = iot_data['room']['department']['name']
        
        # LOG INICIAL RICO (Movido para cá para ter os nomes)
        self.logger.info(f"Solicitando abertura da Porta '{iot_name}' na Sala '{room_name}' ({dept_name}).")
        
        command_topic = f"{dept_name}/{room_name}/{iot_name}/comando"

        # 2. Verifica Permissões
        if user_data.get('tipo_vinculo') != 'Servidor':
            resp_perm = requests.get(
                f"{DB_SERVICE_URL}/user-permissions/", 
                params={'user': user_data['id'], 'room': iot_data['room']['id']}, 
                headers=headers, timeout=5
            )
            if not resp_perm.json():
                self.logger.warning(f"Acesso negado para '{iot_name}'.")
                return {'error': 'Acesso negado', 'status_code': 403}

        # 3. Envia Comando
        payload_bridge = {
            "action": "publish",
            "topic": command_topic,
            "payload": json.dumps({"command": "open", "requested_by": self.current_user}),
            "requested_by": self.current_user,
            "qos": 1,
            "meta": {"cid": self.cid}
        }
        app.send_task('process_command', args=[payload_bridge], queue='door_commands')
        
        self.logger.info(f"Comando de abertura enviado para '{iot_name}'.")
        return {"status": "success", "message": "Porta acionada."}

    except Exception as e:
        self.logger.error(f"Falha ao abrir porta: {e}")
        return {'error': str(e), 'status_code': 500}

@app.task(base=StandardTask, bind=True, name='get_door_status_task')
def get_door_status_task(self, user_data, iot_pk):
    try:
        headers = {'X-Correlation-ID': self.cid}
        
        # 1. Busca dados
        resp = requests.get(f"{DB_SERVICE_URL}/iots/{iot_pk}/", headers=headers, timeout=5)
        resp.raise_for_status()
        iot_data = resp.json()

        try:
            dept = iot_data['room']['department']['name']
            room = iot_data['room']['name']
            iot = iot_data['name']
            status_topic = f"{dept}/{room}/{iot}/status"
            
            # LOG RICO
            self.logger.info(f"Consultando sensor em tempo real: Porta '{iot}' em '{room}' ({dept}).")
            
        except KeyError:
            return {"status": "error", "message": "Dados do IoT incompletos"}

        # 2. RPC Call
        payload_bridge = {
            "action": "status",
            "topic": status_topic,
            "requested_by": self.current_user,
            "meta": {"cid": self.cid}
        }

        try:
            sensor_data = rpc_call_bridge(payload_bridge, self.cid)
            self.logger.info(f"Sensor '{iot}' respondeu: {sensor_data}")
            
            return {
                "status": "success",
                "iot_info": {"name": iot, "db_connected": iot_data['status']},
                "sensor_data": sensor_data
            }
        except TimeoutError:
            self.logger.warning(f"Timeout: Sensor '{iot}' sem resposta.")
            return {"status": "error", "message": "Sensor indisponível."}

    except Exception as e:
        self.logger.error(f"Erro ao checar status: {e}")
        return {'error': str(e)}