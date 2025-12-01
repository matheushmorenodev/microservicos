# middleware/app/main.py
import os
import logging
import jwt
import json 
import httpx
from fastapi import FastAPI, Header, HTTPException, status, Request, Depends
from .rpc_client import RpcClient

# ======================================================================================
#                                 CONFIGURAÇÃO INICIAL
# ======================================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    logger.critical("Variável de ambiente 'DJANGO_SECRET_KEY' não definida. Encerrando.")
    raise ValueError("A variável de ambiente 'DJANGO_SECRET_KEY' é obrigatória.")

DB_SERVICE_URL = os.getenv("DB_SERVICE_URL")
if not DB_SERVICE_URL:
    logger.critical("Variável de ambiente 'DB_SERVICE_URL' não definida. Encerrando.")
    raise ValueError("A variável de ambiente 'DB_SERVICE_URL' é obrigatória.")

# ======================================================================================
#                             INICIALIZAÇÃO DO APP
# ======================================================================================

app = FastAPI()

rpc_client = RpcClient('amqp://guest:guest@rabbitmq:5672//')

# ======================================================================================
#                        EVENTOS DE CICLO de VIDA (Estilo @on_event)
# ======================================================================================

@app.on_event("startup")
async def startup_event():
    """
    Inicializa o cliente HTTP e o anexa ao app.state.
    Isto é executado pelo Uvicorn na inicialização.
    """
    # Anexa o cliente HTTP ao 'app.state' para ser acessível em todas as requisições
    app.state.http_client = httpx.AsyncClient(base_url=DB_SERVICE_URL, timeout=5.0)
    logger.info(f"Middleware iniciado. Cliente HTTP pronto para {DB_SERVICE_URL}.")
    logger.info("RpcClient pronto para conectar quando necessário.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Fecha os clientes de forma limpa ao encerrar.
    """
    if hasattr(app.state, 'http_client'):
        await app.state.http_client.aclose()
        logger.info("Cliente HTTP fechado.")
    
    await rpc_client.close()
    logger.info("Conexão RPC fechada.")

# ======================================================================================
#               FUNÇÃO AUXILIAR DE COMUNICAÇÃO COM servico-banco-dados
# ======================================================================================

async def update_iot_status_in_db(request: Request, endpoint: str, payload: dict):
    """
    Envia uma atualização (POST) para o servico-banco-dados de forma "fire-and-forget".
    Usa o cliente HTTP anexado ao app.state.
    """
    # Acessa o cliente HTTP a partir do estado do app, via objeto 'request'
    client = request.app.state.http_client
    if not client:
        logger.error("Cliente HTTP não encontrado no app.state. Impossível atualizar status do IoT.")
        return

    try:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status() 
        logger.info(f"Status do IoT atualizado com sucesso em {endpoint}.")
    
    except httpx.RequestError as e:
        logger.warning(f"AVISO: Falha de comunicação ao atualizar status do IoT em {e.request.url!r}: {e}")
    except httpx.HTTPStatusError as e:
        logger.warning(f"AVISO: servico-banco-dados retornou erro {e.response.status_code} ao atualizar status do IoT: {e.response.text}")
    except Exception as e:
        logger.error(f"Erro inesperado em update_iot_status_in_db: {e}")

# ======================================================================================
#                         AUTENTICAÇÃO E INJEÇÃO DE DEPENDÊNCIA
# ======================================================================================

def get_user_from_token(token: str) -> dict:
    """Decodifica o token JWT e retorna o payload ou levanta uma HTTPException."""
    try:
        clean_token = token.split(" ")[1]
        payload = jwt.decode(
            clean_token, 
            SECRET_KEY, 
            algorithms=["HS256"],
            options={"leeway": 10} 
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.warning(f"Tentativa de acesso com token expirado: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, faça login novamente.",
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Tentativa de acesso com token inválido: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {e}",
        )
    except Exception as e:
        logger.error(f"Erro inesperado ao processar token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível processar o token de autorização.",
        )

async def get_current_user(request: Request, authorization: str = Header(None)) -> dict:
    """
    Função de dependência do FastAPI para validar o token e extrair os dados do usuário.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token de autorização não fornecido"
        )
    
    user_payload = get_user_from_token(authorization)
    user_payload['source_ip'] = request.client.host
    return user_payload

# ======================================================================================
#                                 ENDPOINTS DA API (Rotas Seguras)
# ======================================================================================

@app.get("/api/departments/")
async def list_departments(user: dict = Depends(get_current_user)):
    logger.info(f"Usuário '{user.get('username')}' solicitou a lista de departamentos.")
    response = await rpc_client.call('list_departments_task', user, queue='permission_queue')
    if 'error' in response:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])
    return response.get('result')

@app.get("/api/departments/{department_pk}/rooms/")
async def list_rooms(department_pk: int, user: dict = Depends(get_current_user)):
    logger.info(f"Usuário '{user.get('username')}' solicitou salas do departamento {department_pk}.")
    response = await rpc_client.call('list_rooms_task', (user, department_pk), queue='permission_queue')
    if response.get('error'):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])
    return response.get('result')

@app.get("/api/rooms/{room_pk}/iots/")
async def list_iots(room_pk: int, user: dict = Depends(get_current_user)):
    logger.info(f"Usuário '{user.get('username')}' solicitou IoTs da sala {room_pk}.")
    response = await rpc_client.call('list_iots_task', (user, room_pk), queue='permission_queue')
    if response.get('error'):
        if "Acesso negado" in response['error']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=response['error'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])
    return response.get('result')

@app.post("/api/iots/{iot_pk}/open/")
async def open_door(iot_pk: int, user: dict = Depends(get_current_user)):
    logger.info(f"Usuário '{user.get('username')}' solicitou abertura da porta para o IoT {iot_pk}.")
    response = await rpc_client.call('open_door_task', (user, iot_pk), queue='permission_queue')
    if response.get('error'):
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])
    return response

@app.get("/api/iots/{iot_pk}/status/")
async def get_iot_status(iot_pk: int, user: dict = Depends(get_current_user)):
    logger.info(f"Usuário '{user.get('username')}' solicitou status do IoT {iot_pk}.")
    response = await rpc_client.call('get_door_status_task', (user, iot_pk), queue='permission_queue')
    if response.get('error'):
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])
        
    return response

# ======================================================================================
#                       ENDPOINTS DA API (Webhooks MQTT)
# ======================================================================================
@app.post("/api/iots/connected/")
async def iot_connected(request: Request):
    """
    Webhook chamado pelo broker MQTT quando um cliente (IoT) se conecta.
    """
    try:
        payload = await request.json()
        client_id_string = payload.get('clientid')

        if not client_id_string or client_id_string == "door_service_bridge":
            logger.info(f"Evento de conexão ignorado para o clientid: {client_id_string}")
            return {"status": "success", "detail": "Ignored service client"}

        try:
            name_department, name_room, name_iot = client_id_string.split('/')
            logger.info(f"Parse do clientid: Department='{name_department}', Room='{name_room}', IoT='{name_iot}'")
            topic_to_subscribe = f"{name_department}/{name_room}/{name_iot}/status"
            
            command_payload = {
                "action": "subscribe",
                "topic": topic_to_subscribe,
                "qos": 1
            }
            
            # --- TAREFA 1: Enviar comando de subscribe (RPC) ---
            await rpc_client.publish_fire_and_forget(
                'process_command', 
                command_payload,
                queue='door_commands'
            )
            logger.info(f"Tarefa 'subscribe' [Fire/Forget] enviada para 'door_commands' para o tópico: {topic_to_subscribe}")

            # --- TAREFA 2: Atualizar status no DB (HTTP) ---
            db_payload = {
                "name_iot": name_iot,
                "name_room": name_room,
                "name_department": name_department
            }
            # Passa o 'request' para a função helper
            await update_iot_status_in_db(
                request=request, 
                endpoint="/api/iot-connection/connect/", 
                payload=db_payload
            )

        except ValueError:
            logger.warning(f"Formato inesperado do clientid: {client_id_string}. Esperado 'name_department/name_room/name_iot'.")
            return {"status": "error", "detail": "Invalid clientid format"}, status.HTTP_200_OK

        except Exception as publish_e:
            logger.exception(f"Falha ao processar conexão para {client_id_string}: {publish_e}")
            return {"status": "error", "detail": "Failed to enqueue tasks"}, status.HTTP_200_OK
        
        return {"status": "success"}

    except Exception as e:
        logger.exception("Erro crítico ao processar webhook 'connected'")
        return {"status": "error", "detail": str(e)}, status.HTTP_200_OK

@app.post("/api/iots/disconnected/")
async def iot_disconnected(request: Request):
    """
    Webhook chamado pelo broker MQTT quando um cliente (IoT) se desconecta.
    """
    try:
        payload = await request.json()
        client_id_string = payload.get('clientid')

        if not client_id_string or client_id_string == "door_service_bridge":
            logger.info(f"Evento de desconexão ignorado para o clientid: {client_id_string}")
            return {"status": "success", "detail": "Ignored service client"}

        logger.info(f"Cliente desconectado: {client_id_string}")

        try:
            name_department, name_room, name_iot = client_id_string.split('/')
            topic_to_unsubscribe = f"{name_department}/{name_room}/{name_iot}/status"

            # 1. Atualizar o iot no banco de dados (via HTTP)
            db_payload = {
                "name_iot": name_iot,
                "name_room": name_room,
                "name_department": name_department
            }
            # Passa o 'request' para a função helper
            await update_iot_status_in_db(
                request=request, 
                endpoint="/api/iot-connection/disconnect/", 
                payload=db_payload
            )

            # 2. Enviar um comando do tipo unsubscribe (via RPC)
            command_payload = {
                "action": "unsubscribe",
                "topic": topic_to_unsubscribe
            }
            await rpc_client.publish_fire_and_forget(
                'process_command', 
                command_payload,
                queue='door_commands'
            )
            logger.info(f"Tarefa 'unsubscribe' [Fire/Forget] enviada para 'door_commands' para o tópico: {topic_to_unsubscribe}")

            return {"status": "success"}

        except ValueError:
            logger.warning(f"Formato inesperado do clientid na desconexão: {client_id_string}.")
        except Exception as e:
            logger.exception(f"Erro ao processar desconexão para {client_id_string}: {e}")
            
        return {"status": "processed_with_errors"}

    except Exception as e:
        logger.exception("Erro crítico ao processar webhook 'disconnected'")
        return {"status": "error", "detail": str(e)}, status.HTTP_200_OK