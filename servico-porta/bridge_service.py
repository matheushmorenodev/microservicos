import os
import sys
import logging
import asyncio
import json
import uuid
from typing import Optional, Dict, Any

import aio_pika
import aiohttp
from aio_pika.abc import AbstractIncomingMessage

import config
from mqtt.mqtt_client import AsyncMQTTBridgeClient
from db.db_client import fetch_active_iot_topics
from amqp.amqp_publisher import AMQPPublisher

# ==============================================================================
# CONFIGURAÇÃO DE LOGS
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger("aio_pika").setLevel(logging.WARNING)
logging.getLogger("aiomqtt").setLevel(logging.WARNING)

logger = logging.getLogger("ServicoPorta")

class BridgeService:
    def __init__(self):
        self.service_name = "ServicoPorta"
        self.amqp_connection: Optional[aio_pika.RobustConnection] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.log_publisher: Optional[AMQPPublisher] = None
        
        self.mqtt_client = AsyncMQTTBridgeClient(
            host=config.MQTT_BROKER_HOST,
            port=config.MQTT_BROKER_PORT
        )
        self._shutdown_event = asyncio.Event()

    async def _log(self, level: str, message: str, cid: str = "SYSTEM", user: str = "SYSTEM"):
        """Centraliza logs locais e remotos."""
        full_message = f"[{cid}] [User: {user}] {message}"
        logger.log(getattr(logging, level.upper()), full_message)

        if self.log_publisher:
            try:
                celery_payload = {
                    "task": "save_log_task",
                    "id": str(uuid.uuid4()),
                    "args": [self.service_name, level.upper(), full_message, cid],
                    "kwargs": {}, "retries": 0, "eta": None
                }
                asyncio.create_task(self.log_publisher.publish(celery_payload))
            except Exception:
                pass

    # ==========================================================================
    # CONSUMIDOR AMQP
    # ==========================================================================
    async def start_amqp_consumer(self):
        await self._log("INFO", "Iniciando consumidor AMQP...")
        try:
            channel = await self.amqp_connection.channel()
            await channel.set_qos(prefetch_count=1)
            queue = await channel.declare_queue(config.AMQP_COMMAND_QUEUE, durable=True)

            async def on_message(message: AbstractIncomingMessage):
                async with message.process():
                    try:
                        raw_body = json.loads(message.body)
                        payload = None
                        cid = "UNKNOWN"
                        
                        # Extração de Payload (Celery/Raw)
                        if isinstance(raw_body, list) and raw_body:
                            payload = raw_body[0]
                            if isinstance(payload, list) and payload: payload = payload[0]
                        elif isinstance(raw_body, dict):
                            if "args" in raw_body:
                                args = raw_body.get("args", [])
                                if args: payload = args[0]
                                cid = raw_body.get("id") or cid
                            else:
                                payload = raw_body

                        if isinstance(payload, dict):
                            cid = payload.get("meta", {}).get("cid") or cid
                            user = payload.get("requested_by") or payload.get("user") or "SYSTEM"
                            
                            result = await self.process_command(payload, cid, user)
                            
                            if message.reply_to and result is not None:
                                response_body = json.dumps(result).encode('utf-8')
                                await channel.default_exchange.publish(
                                    aio_pika.Message(
                                        body=response_body,
                                        correlation_id=message.correlation_id,
                                        content_type='application/json'
                                    ),
                                    routing_key=message.reply_to
                                )
                                # Log de confirmação RPC removido para não poluir, 
                                # pois o process_command já vai logar detalhado.
                        else:
                            await self._log("ERROR", f"Payload inválido: {raw_body}", cid)

                    except Exception as e:
                        await self._log("ERROR", f"Erro AMQP: {e}", cid)

            await queue.consume(on_message)
            await self._log("INFO", f"Ouvindo fila '{config.AMQP_COMMAND_QUEUE}'")
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            await self._log("INFO", "Cancelado.")
        except Exception as e:
            await self._log("CRITICAL", f"Erro fatal: {e}")
            self._shutdown_event.set()

    # ==========================================================================
    # LÓGICA DE NEGÓCIO COM PARSE DE TÓPICO
    # ==========================================================================
    async def process_command(self, command: Dict, cid: str, user: str) -> Any:
        action = command.get("action")
        topic = command.get("topic")

        # --- 1. Extração Inteligente do Contexto do Tópico ---
        # Tópico esperado: Departamento/Sala/IoT/Comando
        dept, room, iot = "?", "?", "?"
        try:
            if topic:
                parts = topic.split('/')
                if len(parts) >= 3:
                    dept = parts[0]
                    room = parts[1]
                    iot = parts[2]
        except Exception:
            pass # Se falhar o split, usa "?"

        try:
            # --- 2. Lógica por Ação ---

            if action == "publish":
                payload = command.get("payload", "")
                
                # Formata payload para log
                payload_str = str(payload)
                if isinstance(payload, dict): 
                    payload = json.dumps(payload)
                    payload_str = json.dumps(payload) # Para log
                elif not isinstance(payload, str): 
                    payload = str(payload)

                # LOG DETALHADO
                await self._log("INFO", f"Enviando comando para Porta '{iot}' (Sala {room}, Dept {dept}). Payload: {payload_str}", cid, user)
                
                await self.mqtt_client.publish(topic, payload, int(command.get("qos", 1)), False)
                return {"status": "published"}

            elif action == "subscribe":
                await self._log("INFO", f"Iniciando monitoramento da Porta '{iot}' (Sala {room}).", cid, user)
                await self.mqtt_client.subscribe(topic, int(command.get("qos", 1)), managed=True)
                return {"status": "subscribed"}

            elif action == "unsubscribe":
                await self._log("INFO", f"Parando monitoramento da Porta '{iot}'.", cid, user)
                await self.mqtt_client.unsubscribe(topic)
                return {"status": "unsubscribed"}
            
            elif action == "status":
                last_msg = self.mqtt_client.get_last_message(topic)
                
                if last_msg is None:
                    # await self._log("WARNING", f"Consulta status Porta '{iot}' (Sala {room}): Cache vazio/Sem dados.", cid, user)
                    return {"status": "nodata", "value": None}
                
                # await self._log("INFO", f"Consulta status Porta '{iot}' (Sala {room}, Dept {dept}): Valor atual '{last_msg}'", cid, user)
                
                try:
                    return json.loads(last_msg)
                except:
                    return {"status_door": last_msg}
            
            else:
                await self._log("WARNING", f"Ação desconhecida: {action}", cid, user)
                return {"error": "unknown_action"}

        except Exception as e:
            await self._log("ERROR", f"Falha ao executar '{action}' no IoT '{iot}': {e}", cid, user)
            return {"error": str(e)}

    # ==========================================================================
    # SYNC & START
    # ==========================================================================
    async def run_periodic_sync(self):
        await self._log("INFO", "Iniciando Sync Loop.")
        while not self._shutdown_event.is_set():
            try:
                if self.http_session:
                    topics = await fetch_active_iot_topics(self.http_session)
                    if topics:
                        await self.mqtt_client.sync_subscriptions(topics)
                        # Log de sistema menos verboso
                        # await self._log("INFO", f"Sync: {len(topics)} tópicos.", "SYSTEM", "SYSTEM")
            except Exception as e:
                logger.error(f"Erro Sync: {e}")
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=config.SYNC_INTERVAL_SECONDS)
            except asyncio.TimeoutError: continue

    async def start(self):
        await self._log("INFO", "Inicializando...")
        while not self._shutdown_event.is_set():
            try:
                self.amqp_connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
                await self._log("INFO", "RabbitMQ Conectado.")
                break
            except Exception:
                await asyncio.sleep(5)

        self.http_session = aiohttp.ClientSession()
        self.log_publisher = AMQPPublisher(self.amqp_connection, config.AMQP_LOG_QUEUE)
        await self.log_publisher.setup()

        tasks = [
            asyncio.create_task(self.mqtt_client.connect(log_callback=lambda l, m: self._log(l, m))),
            asyncio.create_task(self.start_amqp_consumer()),
            asyncio.create_task(self.run_periodic_sync())
        ]
        await self._log("INFO", "Serviço totalmente iniciado.")
        await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self):
        await self._log("INFO", "Encerrando...")
        self._shutdown_event.set()
        if self.mqtt_client: await self.mqtt_client.disconnect()
        if self.amqp_connection: await self.amqp_connection.close()
        if self.http_session: await self.http_session.close()
        if self.log_publisher: await self.log_publisher.close()

if __name__ == "__main__":
    service = BridgeService()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(service.start())
    except KeyboardInterrupt: pass
    finally:
        loop.run_until_complete(service.shutdown())
        loop.close()