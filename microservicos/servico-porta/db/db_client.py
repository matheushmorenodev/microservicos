# servico-porta/db/db_client.py
import logging
from typing import Set

import aiohttp
import config

logger = logging.getLogger("DBClient")

async def fetch_active_iot_topics(session: aiohttp.ClientSession) -> Set[str]:
    """
    Busca IoTs ativos no servico-banco-dados e retorna um set de tópicos MQTT.
    """
    url = f"{config.DB_SERVICE_URL}/iots/"
    params = {'status': 'true'}
    
    logger.info(f"Buscando IoTs ativos em {url}...")
    
    try:
        async with session.get(url, params=params, timeout=10) as response:
            response.raise_for_status()
            active_iots = await response.json()
            
            logger.info(f"{len(active_iots)} IoTs ativos encontrados.")
            
            topics = set()
            for iot in active_iots:
                iot_name = iot.get('name')
                room = iot.get('room', {})
                room_name = room.get('name')
                department = room.get('department', {})
                dept_name = department.get('name')

                if iot_name and room_name and dept_name:
                    topic = f"{dept_name}/{room_name}/{iot_name}/status"
                    topics.add(topic)
                else:
                    logger.warning(f"IoT {iot.get('id')} ignorado: dados de sala/departamento incompletos.")
                    
            logger.info(f"{len(topics)} tópicos únicos encontrados para inscrição.")
            return topics
            
    except aiohttp.ClientError as e:
        logger.error(f"Erro ao comunicar com servico-banco-dados em {url}: {e}")
        raise 
    except Exception as e:
        logger.error(f"Erro inesperado ao processar resposta do servico-banco-dados: {e}")
        raise