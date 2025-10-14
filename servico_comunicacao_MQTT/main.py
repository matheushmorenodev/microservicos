import pika
import paho.mqtt.client as mqtt
import os
import json
import time
import sys

# --- Configurações a partir de variáveis de ambiente ---
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_QUEUE = os.getenv('RABBITMQ_QUEUE', 'mqtt_commands')
MQTT_BROKER_HOST = os.getenv('MQTT_BROKER_HOST', 'emqx')
MQTT_BROKER_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))

print("--- SERVIÇO DE COMUNICAÇÃO MQTT INICIADO ---")

# --- Funções de Callback para o Cliente MQTT ---
def on_connect(client, userdata, flags, reason_code, properties):
    """Callback para a nova API v2 do paho-mqtt."""
    if reason_code == 0:
        print("[MQTT] Conectado ao Broker MQTT com sucesso!")
    else:
        print(f"[MQTT] Falha ao conectar ao Broker MQTT, código de retorno: {reason_code}\n")

def on_message(client, userdata, msg):
    """
    Callback para quando uma mensagem é recebida de um tópico MQTT inscrito.
    Aqui, você pode decidir o que fazer com a mensagem, como encaminhá-la
    de volta para outra fila do RabbitMQ.
    """
    print(f"[MQTT] Mensagem recebida no tópico {msg.topic}: {str(msg.payload.decode('utf-8'))}")
    # TODO: Implementar lógica para reenviar para o RabbitMQ se necessário.

# --- Função de Callback para o Consumidor RabbitMQ ---
def process_amqp_message(ch, method, properties, body):
    print(f"[AMQP] Comando recebido da fila '{RABBITMQ_QUEUE}'.")
    try:
        command = json.loads(body)
        action = command.get('action')
        topic = command.get('topic')
        
        if not action or not topic:
            print("[AMQP] Erro: Comando inválido. 'action' e 'topic' são obrigatórios.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        if action == 'publish':
            payload = command.get('payload', '{}')
            qos = int(command.get('qos', 0))
            retain = bool(command.get('retain', False))
            
            mqtt_client.publish(topic, payload, qos, retain)
            print(f"[MQTT] Publicado no tópico '{topic}': {payload}")

        elif action == 'subscribe':
            qos = int(command.get('qos', 0))
            mqtt_client.subscribe(topic, qos)
            print(f"[MQTT] Inscrito no tópico '{topic}'")
        
        else:
            print(f"[AMQP] Erro: Ação '{action}' desconhecida.")

    except json.JSONDecodeError:
        print("[AMQP] Erro: Falha ao decodificar a mensagem JSON.")
    except Exception as e:
        print(f"[AMQP] Erro inesperado ao processar comando: {e}")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


# --- Função Principal ---
def main():
    # Conexão com RabbitMQ com retentativas
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            print("Conectado ao RabbitMQ e fila declarada.")
            break
        except pika.exceptions.AMQPConnectionError:
            print("Não foi possível conectar ao RabbitMQ. Tentando novamente em 5 segundos...")
            time.sleep(5)

    # Configuração do consumidor
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=process_amqp_message)

    print('Aguardando por comandos na fila do RabbitMQ...')
    # Inicia o consumo em uma thread não-bloqueante
    channel.start_consuming()


if __name__ == '__main__':
    # 1. Inicializa e conecta ao MQTT Broker
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt_communication_service_bridge")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    print(f"[MQTT] Conectando ao broker em {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    mqtt_client.loop_start()

    # 2. Conecta ao RabbitMQ com retentativas e logs detalhados
    while True:
        try:
            print(f"[AMQP] Conectando ao RabbitMQ em {RABBITMQ_HOST}...")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            
            print(f"[AMQP] Conectado! Declarando fila '{RABBITMQ_QUEUE}'...")
            channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
            
            print("[AMQP] Configurando consumidor...")
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=process_amqp_message)
            
            print(f"[*] Aguardando por comandos na fila '{RABBITMQ_QUEUE}'. Para sair, pressione CTRL+C")
            channel.start_consuming() # Esta chamada é bloqueante

        except pika.exceptions.AMQPConnectionError as e:
            print(f"[AMQP] Erro de conexão: {e}. Tentando novamente em 5 segundos...")
            time.sleep(5)
        except Exception as e:
            print(f"[CRITICAL] Um erro inesperado ocorreu: {e}. Encerrando.")
            break # Sai do loop em caso de erro não previsto

    # Cleanup
    mqtt_client.loop_stop()
    print("--- SERVIÇO DE COMUNICAÇÃO MQTT ENCERRADO ---")