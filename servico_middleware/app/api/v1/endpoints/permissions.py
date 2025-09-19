# Apenas o endpoint de permissões
import asyncio
import json
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from app.api.deps import get_rpc_client
from app.services.rpc_client import RPCClient

router = APIRouter()

@router.get("/permissions/check")
async def check_permission(
    user_id: str,
    port_id: str,
    rpc_client: RPCClient = Depends(get_rpc_client) # Magia da Injeção de Dependência!
):
    """
    Endpoint que verifica a permissão de um usuário em uma porta.
    Note como ele está limpo. Ele só orquestra a chamada.
    """
    try:
        message = {"user_id": user_id, "port_id": port_id}
        response_body = await rpc_client.call("permission_queue", message)
        response_data = json.loads(response_body.decode())
        return JSONResponse(status_code=status.HTTP_200_OK, content=response_data)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "O serviço de permissão não respondeu a tempo."},
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Ocorreu um erro interno: {e}"},
        )