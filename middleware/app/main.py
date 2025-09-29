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
        # Remove "Bearer " do início
        clean_token = token.split(" ")[1]
        payload = jwt.decode(clean_token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

@app.get("/api/departments/")
async def list_departments(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token não fornecido")

    user_payload = get_user_from_token(authorization)

    print(f"Enviando tarefa 'list_departments_task' para o usuário {user_payload.get('username')}")

    # Chama a tarefa no worker do serviço de permissão e aguarda a resposta
    response = await rpc_client.call('list_departments_task', user_payload)

    if 'error' in response:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=response['error'])

    return response