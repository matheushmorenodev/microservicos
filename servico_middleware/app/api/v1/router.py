# Agregador de todos os routers da v1
from fastapi import APIRouter
from app.api.v1.endpoints import permissions

api_router = APIRouter()
api_router.include_router(permissions.router, prefix="/v1", tags=["permissions"])