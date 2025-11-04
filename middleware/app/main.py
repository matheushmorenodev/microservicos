# middleware/app/main.py

import os
import logging
import jwt
import json 
from fastapi import FastAPI, Header, HTTPException, status, Request, Depends

# Importe o RpcClient do seu outro arquivo
from .rpc_client import RpcClient

# ======================================================================================
#                                 CONFIGURAÇÃO INICIAL
# ======================================================================================

# 1. Configuração do Logging
# Define o logger para ser usado em todo o aplicativo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Validação da Chave Secreta
# O aplicativo não deve iniciar sem uma chave de segurança definida
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    logger.critical("Variável de ambiente 'DJANGO_SECRET_KEY' não definida. Encerrando.")
    raise ValueError("A variável de ambiente 'DJANGO_SECRET_KEY' é obrigatória.")

# 3. Inicialização do FastAPI e do Cliente RPC
app = FastAPI()
rpc_client = RpcClient('amqp://guest:guest@rabbitmq:5672//')

# ======================================================================================
#                                 EVENTOS DE CICLO DE VIDA
# ======================================================================================

@app.on_event("startup")
async def startup():
    # A conexão com o RabbitMQ agora é "lazy" (preguiçosa), feita na primeira requisição
    logger.info("Middleware iniciado. RpcClient pronto para conectar quando necessário.")

@app.on_event("shutdown")
async def shutdown():
    # Fecha a conexão com o RabbitMQ de forma limpa ao encerrar o app
    logger.info("Middleware encerrando. Fechando conexão RPC.")
    await rpc_client.close()

# ======================================================================================
#                       AUTENTICAÇÃO E INJEÇÃO DE DEPENDÊNCIA
# ======================================================================================

def get_user_from_token(token: str) -> dict:
    """Decodifica o token JWT e retorna o payload ou levanta uma HTTPException."""
    try:
        clean_token = token.split(" ")[1]
        payload = jwt.decode(
            clean_token, 
            SECRET_KEY, 
            algorithms=["HS256"],
            # Lida com pequenas diferenças de relógio entre os contêineres
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
    Esta função será executada antes de cada endpoint que a solicitar.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token de autorização não fornecido"
        )
    
    user_payload = get_user_from_token(authorization)
    # Adiciona o IP de origem ao payload para fins de log
    user_payload['source_ip'] = request.client.host
    return user_payload

# ======================================================================================
#                                     ENDPOINTS DA API
# ======================================================================================

@app.get("/api/departments/")
async def list_departments(user: dict = Depends(get_current_user)):
    """Lista departamentos com base nas permissões do usuário."""
    logger.info(f"Usuário '{user.get('username')}' solicitou a lista de departamentos.")
    
    response = await rpc_client.call(
        'list_departments_task', 
        user, 
        queue='permission_queue'
    )

    if 'error' in response:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')

@app.get("/api/departments/{department_pk}/rooms/")
async def list_rooms(department_pk: int, user: dict = Depends(get_current_user)):
    """Lista as salas de um departamento específico, respeitando as permissões."""
    logger.info(f"Usuário '{user.get('username')}' solicitou salas do departamento {department_pk}.")
    
    response = await rpc_client.call(
        'list_rooms_task', 
        (user, department_pk), 
        queue='permission_queue'
    )

    if response.get('error'):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')

@app.get("/api/rooms/{room_pk}/iots/")
async def list_iots(room_pk: int, user: dict = Depends(get_current_user)):
    """Lista os dispositivos IoT de uma sala específica, respeitando as permissões."""
    logger.info(f"Usuário '{user.get('username')}' solicitou IoTs da sala {room_pk}.")

    response = await rpc_client.call(
        'list_iots_task', 
        (user, room_pk), 
        queue='permission_queue'
    )

    if response.get('error'):
        if "Acesso negado" in response['error']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=response['error'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')

@app.post("/api/iots/{iot_pk}/open/")
async def open_door(iot_pk: int, user: dict = Depends(get_current_user)):
    """Envia um comando para abrir a porta de um dispositivo IoT específico."""
    logger.info(f"Usuário '{user.get('username')}' solicitou abertura da porta para o IoT {iot_pk}.")
    
    response = await rpc_client.call(
        'open_door_task', 
        (user, iot_pk), 
        queue='permission_queue'
    )

    if response.get('error'):
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])

    return response

@app.post("/api/iots/connected/")
async def iot_connected(request: Request):
    try:
        payload = await request.json()

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
                
                try:
                    await rpc_client.publish_fire_and_forget(
                        'process_command', 
                        command_payload,
                        queue='door_commands'
                    )

                    logger.info(f"Tarefa 'subscribe' [Fire/Forget] enviada para 'door_commands' para o tópico: {topic_to_subscribe}")
                except HTTPException as http_e:
                    raise http_e
                except Exception as publish_e:
                    # Pega qualquer outro erro inesperado
                    logger.exception(f"Falha inesperada ao enfileirar tarefa 'subscribe' [Fire/Forget]: {publish_e}")
                    raise HTTPException(status_code=500, detail="Falha ao enfileirar tarefa para o message broker.")
            except ValueError:
                logger.warning(f"Formato inesperado do clientid: {client_id_string}. Esperado 'name_department/name_room/name_iot'.")
                raise HTTPException(status_code=400, detail=f"Formato inválido do clientid: {client_id_string}. Esperado 'name_department/name_room/name_iot'.")
        
        else:
            logger.warning("Webhook recebido sem 'clientid'.")
            raise HTTPException(status_code=400, detail="Payload do webhook não contém 'clientid'.")

        # Se tudo deu certo
        return {"status": "success"}

    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        logger.exception("Erro ao processar webhook")
        raise HTTPException(status_code=500, detail=f"Erro interno ao processar webhook: {str(e)}")

@app.post("/api/iots/disconnected/")
async def iot_disconnected(request: Request):
    try:
        # Lê o corpo da requisição como JSON
        payload = await request.json()

        if 'clientid' in payload:
            client_id_string = payload['clientid']
            logger.info(f"Cliente desconectado clientid: {client_id_string}")

        # Precisamos fazer tres abordagens:
        # 1. Atualizar o iot no banco de dados (via RPC) -> Precisamos estabelecer uma conexão com o Banco de dados -> Atualizar o status(status de conexão do microcontrolador com o broker MQTT) para conectado.
        # 2. Enviar um comando do tipo unsubscribe para fila do door_service para parar de receber dados do status físico do dispositivo (ex: sensor de porta).
        # 3. LOG

        # Aqui você pode processar o conteúdo do webhook
        # Exemplo: repassar para o RabbitMQ via RPC
        # response = await rpc_client.call(
        #     'webhook_handler_task', 
        #     payload,
        #     queue='webhook_queue'
        # )

        # if response.get('error'):
        #     logger.error(f"Erro ao processar webhook: {response['error']}")
        #     raise HTTPException(status_code=500, detail=response['error'])

        return {"status": "success"}

    except Exception as e:
        logger.exception("Erro ao processar webhook")
        raise HTTPException(status_code=400, detail=f"Erro ao processar webhook: {str(e)}")