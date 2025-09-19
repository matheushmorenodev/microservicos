# Ponto de entrada: cria o app FastAPI e o lifespan
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Usa a configuração do nosso arquivo config.py
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    app.state.rabbitmq_connection = connection
    app.state.rabbitmq_channel = channel
    print("Conexão com RabbitMQ estabelecida!")
    
    yield
    
    await app.state.rabbitmq_connection.close()
    print("Conexão com RabbitMQ fechada.")


app = FastAPI(
    title="Gateway Service",
    lifespan=lifespan
)

# Inclui todas as rotas da v1
app.include_router(api_router)

@app.get("/")
def read_root():
    return {"status": "Gateway Service is running"}