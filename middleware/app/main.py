# middleware/app/main.py
import os
import logging
import uuid
import time
import sys
import httpx
from typing import Optional
from contextvars import ContextVar
from fastapi import FastAPI, Header, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from .rpc_client import RpcClient

# ==============================================================================
# 1. SISTEMA DE LOGS BLINDADO (CORREÇÃO DO ERRO KEYERROR)
# ==============================================================================

# ContextVar é thread-safe e async-safe. Armazena o ID da requisição atual.
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="SYSTEM")

class SafeCorrelationIdFilter(logging.Filter):
    """
    Injeta 'correlation_id' em TODOS os logs.
    Se estiver dentro de um request, pega o ID do request.
    Se for log de sistema (startup, uvicorn), usa 'SYSTEM'.
    Isso previne o KeyError.
    """
    def filter(self, record):
        cid = correlation_id_ctx.get("SYSTEM")
        record.correlation_id = cid
        return True

def setup_global_logging():
    """Configura o logger raiz para interceptar Uvicorn, FastAPI e bibliotecas."""
    # Define o formato padrão exigindo correlation_id
    log_format = '%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s | %(message)s'
    formatter = logging.Formatter(log_format)

    # Configura o Handler de Console (Stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # ADICIONA O FILTRO MÁGICO
    console_handler.addFilter(SafeCorrelationIdFilter())

    # Configura o Logger Raiz (pega tudo)
    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler] # Substitui handlers antigos
    root_logger.setLevel(logging.INFO)

    # Ajusta loggers específicos para não duplicar ou poluir
    logging.getLogger("uvicorn.access").handlers = [console_handler]
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").handlers = [console_handler]
    logging.getLogger("uvicorn.error").propagate = False
    
    # Silencia libs ruidosas
    logging.getLogger("aio_pika").setLevel(logging.WARNING)

# Aplica a configuração IMEDIATAMENTE antes de iniciar o app
setup_global_logging()
logger = logging.getLogger("Middleware")

# ==============================================================================
# 2. CONFIGURAÇÃO E VARIÁVEIS
# ==============================================================================

app = FastAPI(title="Middleware Gateway - Padronizado")

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-key')
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://servico-banco-dados:8002/api")

# Cliente RPC (RabbitMQ)
rpc_client = RpcClient('amqp://guest:guest@rabbitmq:5672//')

# ==============================================================================
# 3. MIDDLEWARE DE CORRELATION ID E TRATAMENTO DE ERRO
# ==============================================================================

@app.middleware("http")
async def standardization_middleware(request: Request, call_next):
    # 1. Identificação da Requisição (Correlation ID)
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    
    # Define no contexto (para os logs funcionarem)
    token = correlation_id_ctx.set(cid)
    # Define no estado (para acesso nas rotas)
    request.state.correlation_id = cid
    
    start_time = time.time()
    
    try:
        # Processa a requisição
        response = await call_next(request)
        
        # Injeta headers de rastreamento na resposta
        process_time = time.time() - start_time
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        return response
        
    except Exception as e:
        # TRATAMENTO GLOBAL DE ERRO (CATCH-ALL)
        logger.error(f"Exceção não tratada no middleware: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Erro Interno do Servidor",
                "detail": str(e),
                "meta": {
                    "cid": cid,
                    "timestamp": time.time()
                }
            }
        )
    finally:
        # Limpa o contexto para a próxima requisição não herdar lixo
        correlation_id_ctx.reset(token)

# ==============================================================================
# 4. LIFECYCLE (STARTUP / SHUTDOWN)
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    # Reinicia logger (garantia extra contra uvicorn overrides)
    setup_global_logging()
    
    # Cliente HTTP para chamadas REST ao Django
    app.state.http_client = httpx.AsyncClient(base_url=DB_SERVICE_URL, timeout=10.0)
    logger.info("Middleware iniciado. Clientes configurados.")

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'http_client'):
        await app.state.http_client.aclose()
    await rpc_client.close()
    logger.info("Middleware encerrado com sucesso.")

# ==============================================================================
# 5. AUTH E DEPENDÊNCIAS
# ==============================================================================

import jwt

def get_user_from_token(token: str) -> dict:
    try:
        if not token.startswith("Bearer "):
            raise ValueError("Token deve começar com Bearer")
        clean_token = token.split(" ")[1]
        
        # Decodifica sem verificar assinatura para este exemplo (em prod, use SECRET_KEY)
        # payload = jwt.decode(clean_token, SECRET_KEY, algorithms=["HS256"])
        
        # MOCK TEMPORÁRIO PARA TESTES (Se não tiver JWT real ainda)
        # return {"id": 1, "username": "admin_test", "tipo_vinculo": "Servidor"}
        
        # Implementação real (descomente se tiver token válido):
        payload = jwt.decode(clean_token, options={"verify_signature": False})
        return payload

    except Exception as e:
        logger.warning(f"Erro de Auth: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )

async def get_current_user(request: Request, authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autorização ausente")
    
    user_data = get_user_from_token(authorization)
    user_data['source_ip'] = request.client.host
    return user_data

# ==============================================================================
# 6. ENDPOINTS PADRONIZADOS
# ==============================================================================

@app.get("/api/departments/")
async def list_departments(request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} solicitou departamentos.")
    
    # Chama o Worker via RabbitMQ
    response = await rpc_client.call('list_departments_task', (user,), queue='permission_queue')
    
    # Tratamento de erro vindo do worker
    if isinstance(response, dict) and 'error' in response:
        raise HTTPException(status_code=500, detail=response['error'])

    return {
        "status": "success",
        "data": response.get('result'),
        "meta": {"cid": cid}
    }

@app.get("/api/departments/{department_pk}/rooms/")
async def list_rooms(department_pk: int, request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} listando salas do dept {department_pk}.")
    
    response = await rpc_client.call('list_rooms_task', (user, department_pk), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
        raise HTTPException(status_code=500, detail=response['error'])
        
    return {
        "status": "success",
        "data": response.get('result'),
        "meta": {"cid": cid}
    }

@app.get("/api/rooms/{room_pk}/iots/")
async def list_iots(room_pk: int, request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} listando IoTs da sala {room_pk}.")
    
    response = await rpc_client.call('list_iots_task', (user, room_pk), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
        # Exemplo de tratamento específico de código de erro
        if "Acesso negado" in str(response['error']):
             raise HTTPException(status_code=403, detail=response['error'])
        raise HTTPException(status_code=500, detail=response['error'])
        
    return {
        "status": "success",
        "data": response.get('result'),
        "meta": {"cid": cid}
    }

@app.post("/api/iots/{iot_pk}/open/")
async def open_door(iot_pk: int, request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"ABERTURA SOLICITADA: User {user.get('username')} -> IoT {iot_pk}")
    
    response = await rpc_client.call('open_door_task', (user, iot_pk), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])
    
    return {
        "status": "success",
        "message": response.get("message", "Comando enviado"),
        "data": response,
        "meta": {"cid": cid}
    }

@app.get("/api/iots/{iot_pk}/status/")
async def get_iot_status(iot_pk: int, request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} verificando status do IoT {iot_pk}.")
    
    response = await rpc_client.call('get_door_status_task', (user, iot_pk), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])
        
    return {
        "status": "success",
        "data": response,
        "meta": {"cid": cid}
    }

# ==============================================================================
# 7. WEBHOOKS MQTT (Sem Autenticação de Usuário)
# ==============================================================================

async def update_iot_status_in_db(request: Request, endpoint: str, payload: dict):
    """Helper para atualizar status no DB via HTTP"""
    client = request.app.state.http_client
    try:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        logger.info(f"DB atualizado via webhook: {endpoint}")
    except Exception as e:
        logger.error(f"Falha ao atualizar DB ({endpoint}): {e}")

@app.post("/api/iots/connected/")
async def iot_connected(request: Request):
    """Webhook recebido do EMQX quando um IoT conecta."""
    cid = request.state.correlation_id
    payload = await request.json()
    client_id = payload.get('clientid')
    
    if not client_id or client_id == "door_service_bridge":
        return {"status": "ignored"}

    logger.info(f"Webhook CONNECT: {client_id}")

    try:
        # Parse do ID: Dept/Sala/IoT
        dept, room, iot = client_id.split('/')
        
        # 1. Enviar comando de Subscribe para o Bridge Service (RPC Fire-and-Forget)
        subscribe_cmd = {
            "action": "subscribe",
            "topic": f"{dept}/{room}/{iot}/status",
            "qos": 1
        }
        await rpc_client.publish_fire_and_forget(
            'process_command', 
            subscribe_cmd, 
            queue='door_commands'
        )

        # 2. Atualizar DB
        await update_iot_status_in_db(
            request, 
            "/iot-connection/connect/",
            {"name_iot": iot, "name_room": room, "name_department": dept}
        )

        return {"status": "success", "meta": {"cid": cid}}

    except ValueError:
        logger.warning(f"Client ID mal formatado: {client_id}")
        return {"status": "error", "detail": "Invalid format"}
    except Exception as e:
        logger.error(f"Erro no webhook connect: {e}")
        return {"status": "error", "detail": str(e)}

@app.post("/api/iots/disconnected/")
async def iot_disconnected(request: Request):
    """Webhook recebido do EMQX quando um IoT desconecta."""
    cid = request.state.correlation_id
    payload = await request.json()
    client_id = payload.get('clientid')
    
    if not client_id or client_id == "door_service_bridge":
        return {"status": "ignored"}
        
    logger.info(f"Webhook DISCONNECT: {client_id}")

    try:
        dept, room, iot = client_id.split('/')
        
        # 1. Enviar comando de Unsubscribe
        unsubscribe_cmd = {
            "action": "unsubscribe",
            "topic": f"{dept}/{room}/{iot}/status"
        }
        await rpc_client.publish_fire_and_forget(
            'process_command', 
            unsubscribe_cmd, 
            queue='door_commands'
        )

        # 2. Atualizar DB
        await update_iot_status_in_db(
            request, 
            "/iot-connection/disconnect/",
            {"name_iot": iot, "name_room": room, "name_department": dept}
        )

        return {"status": "success", "meta": {"cid": cid}}

    except Exception as e:
        logger.error(f"Erro no webhook disconnect: {e}")
        return {"status": "error", "detail": str(e)}