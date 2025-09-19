# worker.py
import pika
import json
import time

RABBITMQ_URL = "amqp://guest:guest@localhost/"
PERMISSION_QUEUE = "permission_queue"

def on_request(ch, method, props, body):
    data = json.loads(body)
    user_id = data.get('user_id')
    port_id = data.get('port_id')
    
    print(f"[Worker] Recebida verificação para usuário '{user_id}' na porta '{port_id}'.")
    
    # Lógica de negócio simulada
    time.sleep(1) # Simula trabalho
    
    if user_id == "joao" and port_id == "123":
        response = {"has_permission": True, "user": user_id, "checked_at": time.time()}
    else:
        response = {"has_permission": False, "reason": "Credenciais inválidas"}
        
    # Publica a resposta de volta na fila 'reply_to'
    ch.basic_publish(
        exchange='',
        routing_key=props.reply_to,
        properties=pika.BasicProperties(correlation_id=props.correlation_id),
        body=json.dumps(response)
    )
    ch.basic_ack(delivery_tag=method.delivery_tag)

connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
channel = connection.channel()
channel.queue_declare(queue=PERMISSION_QUEUE)
channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=PERMISSION_QUEUE, on_message_callback=on_request)

print(f"[Worker] Aguardando por requisições na fila '{PERMISSION_QUEUE}'. Pressione CTRL+C para sair.")
channel.start_consuming()