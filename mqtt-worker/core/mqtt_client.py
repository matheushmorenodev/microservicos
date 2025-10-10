# mqtt-worker/core/mqtt_client.py

import paho.mqtt.client as mqtt
import os
import requests
import json

MQTT_BROKER = os.getenv("MQTT_BROKER", "emqx") # Aponta para o serviço do broker no Docker
MQTT_PORT = 1883
DB_SERVICE_URL = "http://db-service:8002/api"

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client(client_id="backend_mqtt_worker")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        print("Cliente MQTT inicializado.")

    def get_topics_from_api(self):
        """
        Busca a lista de IOTs da API do db-service para saber quais tópicos assinar.
        """
        try:
            response = requests.get(f"{DB_SERVICE_URL}/iots/", timeout=5)
            response.raise_for_status()
            iots = response.json()
            
            topics = []
            for iot in iots:
                # Exemplo de tópico: campus/bloco-a/sala-101/porta-principal/status
                # Usamos um formato hierárquico que é uma boa prática em MQTT.
                # O department e room vêm aninhados graças à mudança que fizemos no serializer.
                try:
                    department_name = iot['room']['department']['name'].lower().replace(' ', '-')
                    room_name = iot['room']['name'].lower().replace(' ', '-')
                    iot_name = iot['name'].lower().replace(' ', '-')
                    topics.append(f"campus/{department_name}/{room_name}/{iot_name}/status")
                except (KeyError, TypeError):
                    print(f"AVISO: IOT com ID {iot.get('id')} não tem dados completos de sala/departamento.")
            
            print(f"Tópicos para assinar: {topics}")
            return topics
        except requests.RequestException as e:
            print(f"ERRO: Não foi possível buscar IOTs do db-service: {e}")
            return []

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Conectado ao Broker MQTT com sucesso!")
            topics = self.get_topics_from_api()
            for topic in topics:
                client.subscribe(topic)
                print(f"Inscrito no tópico: {topic}")
        else:
            print(f"Falha ao conectar, código de retorno {rc}\n") 

    def on_message(self, client, userdata, msg):
        """
        Callback para quando uma mensagem é recebida de um dispositivo.
        """
        payload = msg.payload.decode()
        print(f"Mensagem recebida no tópico `{msg.topic}`: {payload}")
        # Futuramente, aqui podemos enviar um log ou atualizar o status de volta para o db-service.

    def on_publish(self, client, userdata, mid):
        print(f"Mensagem com ID {mid} publicada.")

    def start(self):
        try:
            print(f"Tentando conectar ao broker MQTT em {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()  # Inicia o loop em uma thread separada
        except Exception as e:
            print(f"ERRO ao iniciar cliente MQTT: {e}")

    def publish_message(self, topic, message):
        print(f"Publicando no tópico `{topic}`: {message}")
        self.client.publish(topic, message)