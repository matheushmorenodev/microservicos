import os
from .logger import get_logger

logger = get_logger("MQTTManager")

class MQTTManager:
    def __init__(self, mqtt_client):
        self.mqtt_client = mqtt_client
        self.messages = {}

    def _topic(self, department: str, name: str) -> str:
        return f"{department}/door/{name}/status" # Preciso alterar para o tópico correto

    def load_active_topics(self):
        try:
            # ======================================================================================================================== 
            #                           Preciso arrumar aqui para consultar o serviço de banco de dados
            # ======================================================================================================================== 
            # doors = Door.objects.using("default").filter(connection_status=1) 
            # topics = [self._topic(d.department, d.name) for d in doors]
            logger.info(f"Tópicos ativos carregados: {topics}")
            return topics
        except Exception as e:
            logger.error(f"Erro ao buscar portas no banco: {e}")
            return []

    def subscribe_active_doors(self):
        for topic in self.load_active_topics():
            self.mqtt_client.subscribe(topic)
            self.messages[topic] = None

    # ======================================================================================================================== 
    #     Verificar se essas funções são necessárias aqui ou se podem ser transferidas para o serviço de banco de dados
    # ======================================================================================================================== 

    # def handle_door_connection(self, department: str, name: str):
    #     topic = self._topic(department, name)
    #     try:
    #         door, created = Door.objects.using("default").get_or_create(
    #             department=department,
    #             name=name,
    #             defaults={"connection_status": 1}
    #         )
    #         if not created:
    #             door.connection_status = 1
    #             door.save(using="default")

    #         self.mqtt_client.subscribe(topic)
    #         logger.info(f"Porta {department}/{name} conectada e inscrita no tópico {topic}")
    #     except Exception as e:
    #         logger.error(f"Erro ao processar conexão da porta {department}/{name}: {e}")

    # def handle_door_disconnection(self, department: str, name: str):
    #     topic = self._topic(department, name)
    #     try:
    #         door = Door.objects.using("default").get(department=department, name=name)
    #         door.connection_status = 0
    #         door.save(using="default")

    #         self.mqtt_client.unsubscribe(topic)
    #         self.messages.pop(topic, None)
    #         logger.info(f"Porta {department}/{name} desconectada e removida do tópico {topic}")
    #     except Exception as e:
    #         logger.error(f"Erro ao desconectar porta {department}/{name}: {e}")

    def publish_message(self, department: str, name: str, message: str):
        topic = self._topic(department, name)
        self.mqtt_client.publish(topic, message)
