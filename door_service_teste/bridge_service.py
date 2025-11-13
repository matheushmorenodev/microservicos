# door_service_teste/bridge_service.py
import os
import logging
import asyncio
import json
from typing import Optional, Dict, Any

import aio_pika
import aiohttp
from aio_pika.abc import AbstractIncomingMessage

# Importa nossos novos módulos de cliente
import config
from mqtt.mqtt_client import AsyncMQTTBridgeClient
from db.db_client import fetch_active_iot_topics
from amqp.amqp_publisher import AMQPPublisher

# =log =========================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BridgeService")
# =================================================================================

class BridgeService:
    """
    Serviço de bridge assíncrono que conecta AMQP (RabbitMQ) e MQTT.
    """

    def __init__(self):
        self.amqp_connection: Optional[aio_pika.RobustConnection] = None
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.log_publisher: Optional[AMQPPublisher] = None
        self.mqtt_client = AsyncMQTTBridgeClient(
            host=config.MQTT_BROKER_HOST,
            port=config.MQTT_BROKER_PORT
        )
        self._shutdown_event = asyncio.Event()

    async def send_log(self, level: str, message: str):
        """Envia uma mensagem de log para a fila de logs."""
        if self.log_publisher:
            try:
                log_data = {
                    "source": "door_service",
                    "level": level.upper(),
                    "message": message
                }
                await self.log_publisher.publish(log_data)
            except Exception as e:
                logger.error(f"CRITICAL: Falha ao enviar log. Razão: {e}")
        else:
            logger.error("Log publisher não está inicializado.")

    async def sync_subscriptions(self):
        """
        Busca tópicos ativos no db-service e se inscreve neles.
        """
        logger.info("Sincronizando inscrições MQTT...")
        if not self.http_session:
            logger.error("Sessão HTTP não inicializada. Abortando sincronização.")
            return

        try:
            active_topics = await fetch_active_iot_topics(self.http_session)
            if not active_topics:
                logger.warning("Nenhum tópico ativo encontrado para sincronizar.")
                return

            # A classe MQTTBridgeClient é inteligente e só (re)inscreve se necessário
            await self.mqtt_client.sync_subscriptions(active_topics)
            
            message = f"{len(active_topics)} tópicos ativos sincronizados."
            logger.info(message)
            await self.send_log('INFO', message)
            
        except Exception as e:
            logger.exception("Falha crítica durante a sincronização de inscrições.")
            await self.send_log('ERROR', f"Falha na sincronização de tópicos: {e}")

    async def run_periodic_sync(self):
        """Executa a sincronização de tópicos em um loop periódico."""
        try:
            while not self._shutdown_event.is_set():
                await self.sync_subscriptions()
                try:
                    # Espera pelo próximo ciclo ou pelo evento de shutdown
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), 
                        timeout=config.SYNC_INTERVAL_SECONDS
                    )
                except asyncio.TimeoutError:
                    continue # Timeout é esperado, continua o loop
        except asyncio.CancelledError:
            logger.info("Loop de sincronização periódica cancelado.")

    async def _publish_rpc_response(self, reply_to: str, correlation_id: str, response_data: Dict[str, Any]):
        """Publica uma resposta de RPC de volta para o solicitante (de forma robusta)."""
        
        if not self.amqp_connection or self.amqp_connection.is_closed:
            logger.error("Não é possível enviar resposta RPC: Conexão AMQP está fechada.")
            return

        try:
            # Cria um canal temporário apenas para esta resposta.
            # Isto é mais robusto do que reutilizar o canal do consumidor.
            async with self.amqp_connection.channel() as channel:
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(response_data).encode(),
                        correlation_id=correlation_id
                    ),
                    routing_key=reply_to
                )
        except Exception as e:
            logger.error(f"Falha ao enviar resposta RPC para {reply_to}: {e}", exc_info=True)

    async def process_command(self, message: AbstractIncomingMessage):
        """Processa um comando recebido da fila AMQP 'door_commands'."""
        
        async with message.process(requeue=False, ignore_processed=True):  # Auto-ACK/NACK
            response_data = None
            status = "success"
            error_message = None
            command = None  # Variável unificada para o comando

            try:
                command_data = json.loads(message.body.decode())
                logger.info(f"Comando recebido: {command_data}")
                
                # --- INÍCIO DA LÓGICA DE EXTRAÇÃO ---
                # Identifica o formato da mensagem para extrair o comando real.
                
                if isinstance(command_data, dict):
                    # Formato 1 (Ex: 'subscribe' vindo de uma tarefa Celery)
                    # Espera: {'id': ..., 'args': [{'action': 'subscribe', ...}]}
                    args = command_data.get("args", [])
                    if args and isinstance(args, list) and len(args) > 0:
                        command = args[0] # Pega o primeiro comando da lista 'args'
                    
                elif isinstance(command_data, list):
                    # Formato 2 (Ex: 'publish' vindo de args diretos)
                    # Espera: [[{'action': 'publish', ...}], {}, {...}]
                    if len(command_data) > 0 and isinstance(command_data[0], list) and len(command_data[0]) > 0:
                        command = command_data[0][0] # Pega o primeiro comando da primeira lista
                
                # Validação final
                if not command or not isinstance(command, dict):
                    raise ValueError(f"Não foi possível extrair um dicionário de comando válido. Dados recebidos: {command_data}")
                # --- FIM DA LÓGICA DE EXTRAÇÃO ---

                
                # Todo o código agora usa a variável 'command'
                action = command.get("action")
                topic = command.get("topic")

                if not action:
                    raise ValueError("O dicionário de comando não contém a chave 'action'.")

                log_msg = f"Processando comando: {action}"
                if topic:
                    log_msg += f" para o tópico: {topic}"
                logger.info(log_msg)

                if not topic and action != "status_all":  # Exceção para um status geral
                    raise ValueError("Campo 'topic' é obrigatório para esta ação.")

                if action == "publish":
                    # CORREÇÃO: Lendo 'payload', 'qos', 'retain' do 'command'
                    payload = command.get("payload", "{}")
                    qos = int(command.get("qos", 1))
                    retain = bool(command.get("retain", False))
                    await self.mqtt_client.publish(topic, payload, qos, retain)
                    await self.send_log('INFO', f"Publicado em '{topic}': {payload}")

                elif action == "subscribe":
                    # CORREÇÃO: Lendo 'qos' do 'command'
                    qos = int(command.get("qos", 1))
                    await self.mqtt_client.subscribe(topic, qos)
                    await self.send_log('INFO', f"Inscrito no tópico: '{topic}'")

                elif action == "unsubscribe":
                    await self.mqtt_client.unsubscribe(topic)
                    await self.send_log('INFO', f"Inscrição cancelada no tópico: '{topic}'")

                elif action == "status":
                    response_data = self.mqtt_client.get_last_message(topic)
                    logger.info(f"Retornando último status do tópico '{topic}': {response_data}")
                
                elif action == "status_all":
                    response_data = self.mqtt_client.get_all_last_messages()
                    logger.info(f"Retornando status de todos os tópicos.")

                else:
                    logger.warning(f"Ação desconhecida recebida: {action}")
                    await self.send_log('WARNING', f"Ação desconhecida: {action}")
                    raise ValueError(f"Ação desconhecida: {action}")

            except Exception as e:
                logger.exception(f"Erro ao processar comando: {e}")
                status = "error"
                error_message = str(e)
                await self.send_log('ERROR', f"Erro ao processar comando: {error_message}")
                # A mensagem será "nackada" automaticamente pelo 'async with'

            # Se for uma chamada RPC (tiver reply_to), envia a resposta
            if message.reply_to:
                rpc_response = {
                    "status": status,
                    "data": response_data,
                    "error": error_message
                }
                # CORREÇÃO: Chamada para o método RPC robusto (sem 'message.channel')
                await self._publish_rpc_response(
                    message.reply_to,
                    message.correlation_id,
                    rpc_response
                )

    async def start_amqp_consumer(self):
        """Inicia o consumidor da fila de comandos AMQP."""
        logger.info("Iniciando consumidor AMQP...")
        try:
            channel = await self.amqp_connection.channel()
            # Garante que pegamos apenas uma mensagem por vez para processamento
            await channel.set_qos(prefetch_count=1) 
            
            queue = await channel.declare_queue(
                config.AMQP_COMMAND_QUEUE,
                durable=True
            )
            
            logger.info(f"Consumidor AMQP pronto. Aguardando mensagens em '{config.AMQP_COMMAND_QUEUE}'")
            await queue.consume(self.process_command)
            
            # Espera pelo evento de shutdown
            await self._shutdown_event.wait()
            
        except asyncio.CancelledError:
            logger.info("Consumidor AMQP cancelado.")
        except Exception as e:
            logger.critical(f"Erro fatal no consumidor AMQP: {e}", exc_info=True)
            self._shutdown_event.set() # Sinaliza para outras tarefas pararem

    async def start(self):
        """Inicia todos os componentes do serviço."""
        logger.info("Iniciando BridgeService...")
        try:
            # 1. Conexão AMQP
            self.amqp_connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
            logger.info("Conectado ao RabbitMQ.")
            
            # 2. Sessão HTTP
            self.http_session = aiohttp.ClientSession()
            logger.info("Sessão HTTP (aiohttp) criada.")
            
            # 3. Publisher de Logs
            self.log_publisher = AMQPPublisher(self.amqp_connection, config.AMQP_LOG_QUEUE)
            await self.log_publisher.setup()
            logger.info(f"Publisher de logs pronto para fila '{config.AMQP_LOG_QUEUE}'.")

            # 4. REMOVA a linha 'self.mqtt_client.set_log_callback(...)'
            
            # 5. Inicia as tarefas de background
            logger.info("Iniciando tarefas de background (MQTT Connect, MQTT Listener, AMQP Consumer, Sync Loop)...")
            
            # **AQUI ESTÁ A CORREÇÃO**
            # Vamos passar o lambda para o método connect() quando criamos a task
            mqtt_task = asyncio.create_task(
                self.mqtt_client.connect(
                    log_callback=lambda lvl, msg: self.send_log(lvl, msg)
                )
            )
            
            # Tarefa para sincronização periódica de tópicos
            sync_task = asyncio.create_task(self.run_periodic_sync())
            
            # Tarefa principal: consumir AMQP (que cria a door_commands)
            amqp_consumer_task = asyncio.create_task(self.start_amqp_consumer())
            
            await self.send_log("INFO", "BridgeService iniciado com sucesso.")

            # Espera todas as tarefas terminarem
            await asyncio.gather(
                mqtt_task,   # <-- Tarefa de conexão MQTT
                sync_task,
                amqp_consumer_task
            )

        except asyncio.CancelledError:
            logger.info("Tarefa 'start' do BridgeService foi cancelada.")
        except Exception as e:
            logger.critical(f"Erro fatal ao iniciar o serviço: {e}", exc_info=True)
            self._shutdown_event.set() 
        finally:
            logger.info("Encerrando BridgeService...")
            await self.shutdown()

    async def shutdown(self):
        """Realiza o graceful shutdown de todos os componentes."""
        if self._shutdown_event.is_set():
            return # Shutdown já em progresso
            
        self._shutdown_event.set()
        logger.info("Iniciando graceful shutdown...")
        
        if self.mqtt_client:
            await self.mqtt_client.disconnect()
        
        if self.log_publisher:
            await self.log_publisher.close()
            
        if self.amqp_connection:
            await self.amqp_connection.close()
            
        if self.http_session:
            await self.http_session.close()
            
        logger.info("Shutdown completo.")

# Ponto de entrada
if __name__ == "__main__":
    service = BridgeService()
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(service.start())
    except KeyboardInterrupt:
        logger.info("Recebido sinal de interrupção (Ctrl+C). Encerrando...")
    finally:
        loop.run_until_complete(service.shutdown())
        logger.info("Aplicação encerrada.")