# middleware/app/main.py
from fastapi import FastAPI, Header, HTTPException, status
from .rpc_client import RpcClient
import jwt
import os

app = FastAPI()
rpc_client = RpcClient('amqp://guest:guest@rabbitmq:5672//')


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'default-insecure-key-for-dev')

@app.on_event("startup")
async def startup():
    await rpc_client.connect()

def get_user_from_token(token: str):
    try:
        clean_token = token.split(" ")[1]
        # Adicione um 'leeway' de 10 segundos para lidar com pequenas diferenças de relógio entre os contêineres
        payload = jwt.decode(
            clean_token, 
            SECRET_KEY, 
            algorithms=["HS256"],
            options={"leeway": 10} # <--- ADICIONE ESTA OPÇÃO
        )
        return payload
    except jwt.ExpiredSignatureError as e: # Captura erro de token expirado
        print(f"ERRO DE DECODIFICAÇÃO: Token expirado! - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
        )
    except jwt.InvalidTokenError as e: # Captura todos os outros erros de token inválido
        print(f"ERRO DE DECODIFICAÇÃO: Token inválido! - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {e}",
        )
    except Exception as e: # Captura qualquer outro erro inesperado
        print(f"ERRO INESPERADO AO PROCESSAR TOKEN: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Erro ao processar token",
        )
# -- ENDPOINT PARA LISTAR DEPARTAMENTOS ---
@app.get("/api/departments/")
async def list_departments(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")

    user_payload = get_user_from_token(authorization)
    #SOMENTE PARA TESTE
    print(f"Papel original do token: {user_payload.get('tipo_vinculo')}")
    user_payload['tipo_vinculo'] = 'Servidor'
    print(f"Forçando papel para: {user_payload.get('tipo_vinculo')}")
    print(f"Enviando tarefa 'list_departments_task' para o usuário {user_payload.get('username')}")

    response = await rpc_client.call('list_departments_task', user_payload)

    if 'error' in response:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')

# --- ENDPOINT PARA LISTAR SALAS ---
@app.get("/api/departments/{department_pk}/rooms/")
async def list_rooms(department_pk: int, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")
    
    user_payload = get_user_from_token(authorization)
    #SOMENTE PARA TESTE
    # print(f"Papel original do token: {user_payload.get('tipo_vinculo')}")
    # user_payload['tipo_vinculo'] = 'Servidor'
    # print(f"Forçando papel para: {user_payload.get('tipo_vinculo')}")
    print(f"Enviando tarefa 'list_rooms_task' para o departamento {department_pk}")
    
    # Chama a tarefa remota, passando o payload E o ID do departamento
    response = await rpc_client.call('list_rooms_task', (user_payload, department_pk))

    if response.get('error'):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')

# --- ENDPOINT PARA LISTAR IOTS ---
@app.get("/api/rooms/{room_pk}/iots/")
async def list_iots(room_pk: int, authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")
    
    user_payload = get_user_from_token(authorization)
    #SOMENTE PARA TESTE
    # print(f"Papel original do token: {user_payload.get('tipo_vinculo')}")
    # user_payload['tipo_vinculo'] = 'Servidor'
    # print(f"Forçando papel para: {user_payload.get('tipo_vinculo')}")
    print(f"Enviando tarefa 'list_iots_task' para a sala {room_pk}")
    
    # Chama a tarefa remota, passando o payload E o ID da sala
    response = await rpc_client.call('list_iots_task', (user_payload, room_pk))

    if response.get('error'):
        # Se o erro for de acesso negado, retorna 403 Forbidden
        if "Acesso negado" in response['error']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=response['error'])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response.get('result')