 # Gerenciamento de configurações (URL do RabbitMQ)
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    RABBITMQ_URL: str
    API_V1_STR: str = "/api/v1"

    class Config:
        env_file = ".env" # Indica para carregar do arquivo .env

settings = Settings()