# door_service_teste/db/db_client.py
import logging
from typing import Set

import aiohttp
import config

logger = logging.getLogger("DBClient")

async def fetch_active_iot_topics(session: aiohttp.ClientSession) -> Set[str]:
    """
    Busca IoTs ativos no db-service e retorna um set de tópicos MQTT.
    """
    url = f"{config.DB_SERVICE_URL}/iots/"
    params = {'status': 'true'}
    
    logger.info(f"Buscando IoTs ativos em {url}...")
    
    try:
        async with session.get(url, params=params, timeout=10) as response:
            response.raise_for_status() # Lança exceção para status 4xx/5xx
            active_iots = await response.json()
            
            logger.info(f"{len(active_iots)} IoTs ativos encontrados.")
            
            topics = set()
            for iot in active_iots:
                name = iot.get('name')
                if name:
                    topics.add(f"campus/geral/{name}/status")
                    
            logger.info(f"{len(topics)} tópicos únicos encontrados para inscrição.")
            return topics
            
    except aiohttp.ClientError as e:
        logger.error(f"Erro ao comunicar com db-service em {url}: {e}")
        raise # Relança a exceção para o chamador (sync_subscriptions) tratar
    except Exception as e:
        logger.error(f"Erro inesperado ao processar resposta do db-service: {e}")
        raise
