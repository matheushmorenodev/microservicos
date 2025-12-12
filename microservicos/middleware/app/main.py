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
import jwt
from fastapi.middleware.cors import CORSMiddleware

# ==============================================================================
# 1. SISTEMA DE LOGS BLINDADO
# ==============================================================================

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="SYSTEM")

class SafeCorrelationIdFilter(logging.Filter):
    def filter(self, record):
        cid = correlation_id_ctx.get("SYSTEM")
        record.correlation_id = cid
        return True

def setup_global_logging():
    log_format = '%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s | %(message)s'
    formatter = logging.Formatter(log_format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SafeCorrelationIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler]
    root_logger.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").handlers = [console_handler]
    logging.getLogger("uvicorn.access").propagate = False
    logging.getLogger("uvicorn.error").handlers = [console_handler]
    logging.getLogger("uvicorn.error").propagate = False
    logging.getLogger("aio_pika").setLevel(logging.WARNING)

setup_global_logging()
logger = logging.getLogger("Middleware")

# ==============================================================================
# 2. CONFIGURAÇÃO
# ==============================================================================

app = FastAPI(title="Middleware Gateway - Padronizado")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem (React, Mobile, etc)
    allow_credentials=True,
    allow_methods=["*"],  # Permite GET, POST, PUT, DELETE, OPTIONS
    allow_headers=["*"],  # Permite enviar Tokens e Correlation-IDs
)


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-key')
DB_SERVICE_URL = os.getenv("DB_SERVICE_URL", "http://servico-banco-dados:8002/api")

rpc_client = RpcClient('amqp://guest:guest@rabbitmq:5672//')

# ==============================================================================
# 3. MIDDLEWARE DE CORRELATION ID
# ==============================================================================

@app.middleware("http")
async def standardization_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    token = correlation_id_ctx.set(cid)
    request.state.correlation_id = cid
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response
        
    except Exception as e:
        logger.error(f"Exceção não tratada: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Erro Interno do Servidor",
                "detail": str(e),
                "meta": {"cid": cid, "timestamp": time.time()}
            }
        )
    finally:
        correlation_id_ctx.reset(token)

# ==============================================================================
# 4. LIFECYCLE
# ==============================================================================

@app.on_event("startup")
async def startup_event():
    setup_global_logging()
    # Cliente HTTP para chamadas REST ao Django
    app.state.http_client = httpx.AsyncClient(base_url=DB_SERVICE_URL, timeout=10.0)
    logger.info("Middleware iniciado. Clientes configurados.")

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'http_client'):
        await app.state.http_client.aclose()
    await rpc_client.close()
    logger.info("Middleware encerrado.")

# ==============================================================================
# 5. AUTH E SINCRONIZAÇÃO DE USUÁRIO (AQUI ESTÁ A MUDANÇA)
# ==============================================================================

def get_user_from_token(token: str) -> dict:
    """Decodifica o token JWT."""
    try:
        if not token.startswith("Bearer "):
            raise ValueError("Token deve começar com Bearer")
        
        clean_token = token.split(" ")[1]
        
        # Em produção, use verify_signature=True com a SECRET_KEY correta
        # payload = jwt.decode(clean_token, SECRET_KEY, algorithms=["HS256"])
        payload = jwt.decode(clean_token, options={"verify_signature": False})
        
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado.")
    except Exception as e:
        logger.warning(f"Erro Auth: {e}")
        raise HTTPException(status_code=401, detail="Token inválido.")

async def sync_user_with_db(request: Request, user_data: dict):
    """
    Sincroniza o usuário do Token com o Banco de Dados.
    Chama o endpoint PUT /users/{id}/ que você configurou no Django.
    """
    client = request.app.state.http_client
    cid = request.state.correlation_id
    
    user_id = user_data.get('id')
    
    # Mapeamento: JWT (tipo_vinculo) -> DB Model (role)
    payload_db = {
        "user_id": user_id,
        "username": user_data.get('username'), # ou matricula
        "role": user_data.get('tipo_vinculo', 'Aluno')
    }

    try:
        # Usamos PUT porque sua View no Django trata PUT como "Atualizar ou Criar"
        response = await client.put(f"/users/{user_id}/", json=payload_db)
        response.raise_for_status()
        # logger.info(f"Usuário {user_id} sincronizado com sucesso.")
        
    except httpx.RequestError as e:
        logger.error(f"Falha de conexão ao sincronizar usuário {user_id}: {e}")
        # Não damos raise aqui para não bloquear o usuário se o DB estiver lento,
        # mas idealmente deveria ser tratado.
    except httpx.HTTPStatusError as e:
        logger.error(f"Erro do DB ao sincronizar usuário {user_id}: {e.response.text}")

async def get_current_user(request: Request, authorization: str = Header(None)) -> dict:
    """
    Dependência principal: Valida Token + Sincroniza DB.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Token ausente")
    
    # 1. Decodifica (Rápido/Síncrono)
    user_data = get_user_from_token(authorization)
    user_data['source_ip'] = request.client.host
    
    # 2. Sincroniza com o Banco (Assíncrono)
    # O await garante que o usuário exista antes de prosseguir para as rotas
    await sync_user_with_db(request, user_data)
    
    return user_data

# ==============================================================================
# 6. ENDPOINTS
# ==============================================================================

@app.get("/api/departments/")
async def list_departments(request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} solicitou departamentos.")
    
    response = await rpc_client.call('list_departments_task', (user,), queue='permission_queue')
    
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
    # logger.info(f"User {user.get('username')} verificando status do IoT {iot_pk}.")
    
    response = await rpc_client.call('get_door_status_task', (user, iot_pk), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
        status_code = response.get('status_code', 500)
        raise HTTPException(status_code=status_code, detail=response['error'])
        
    return {
        "status": "success",
        "data": response,
        "meta": {"cid": cid}
    }

@app.get("/api/iots/")
async def list_all_iots(request: Request, user: dict = Depends(get_current_user)):
    cid = request.state.correlation_id
    logger.info(f"User {user.get('username')} solicitou TODAS as portas (Dashboard).")
    
    # Chama uma nova task no worker para buscar tudo que o usuário tem acesso
    response = await rpc_client.call('list_all_user_iots_task', (user,), queue='permission_queue')
    
    if isinstance(response, dict) and 'error' in response:
         raise HTTPException(status_code=500, detail=response['error'])
         
    return {
        "status": "success",
        "data": response.get('result'),
        "meta": {"cid": cid}
    }    
    

# ==============================================================================
# 7. WEBHOOKS MQTT
# ==============================================================================

async def update_iot_status_in_db(request: Request, endpoint: str, payload: dict):
    client = request.app.state.http_client
    try:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()
        logger.info(f"DB atualizado via webhook: {endpoint}")
    except Exception as e:
        logger.error(f"Falha ao atualizar DB ({endpoint}): {e}")

@app.post("/api/iots/connected/")
async def iot_connected(request: Request):
    cid = request.state.correlation_id
    payload = await request.json()
    client_id = payload.get('clientid')
    
    if not client_id or client_id == "door_service_bridge":
        return {"status": "ignored"}

    logger.info(f"Webhook CONNECT: {client_id}")

    try:
        dept, room, iot = client_id.split('/')
        
        subscribe_cmd = {
            "action": "subscribe",
            "topic": f"{dept}/{room}/{iot}/status",
            "qos": 1
        }
        await rpc_client.publish_fire_and_forget(
            'process_command', subscribe_cmd, queue='door_commands'
        )

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
    cid = request.state.correlation_id
    payload = await request.json()
    client_id = payload.get('clientid')
    
    if not client_id or client_id == "door_service_bridge":
        return {"status": "ignored"}
        
    logger.info(f"Webhook DISCONNECT: {client_id}")

    try:
        dept, room, iot = client_id.split('/')
        
        unsubscribe_cmd = {
            "action": "unsubscribe",
            "topic": f"{dept}/{room}/{iot}/status"
        }
        await rpc_client.publish_fire_and_forget(
            'process_command', unsubscribe_cmd, queue='door_commands'
        )

        await update_iot_status_in_db(
            request, 
            "/iot-connection/disconnect/",
            {"name_iot": iot, "name_room": room, "name_department": dept}
        )
        return {"status": "success", "meta": {"cid": cid}}

    except Exception as e:
        logger.error(f"Erro no webhook disconnect: {e}")
        return {"status": "error", "detail": str(e)}