from celery import shared_task
import requests

DB_SERVICE_URL = "http://db-service:8002/api"

def ensure_user_exists(user_data):
    """
    Função auxiliar que garante que o usuário do token existe no db_service.
    Usa o método PATCH, que cria se não existir ou atualiza se já existir.
    """
    user_id = user_data.get('id')
    if not user_id:
        return

    # Dados que queremos garantir que estão no banco
    data_to_sync = {
        'user_id': user_id,
        'username': user_data.get('username'),
        'role': user_data.get('tipo_vinculo', 'Aluno') # Default para 'Aluno' se não vier no token
    }
    
    try:
        # Usamos o endpoint /api/users/{user_id}/. O DRF ViewSet lida com isso.
        # O método PATCH é ideal aqui: ele atualiza um recurso existente ou pode ser configurado para criar.
        # Vamos usar o método PUT para uma abordagem mais simples de get_or_create no backend.
        requests.put(f"{DB_SERVICE_URL}/users/{user_id}/", json=data_to_sync, timeout=5)
    except requests.RequestException as e:
        # Se a sincronização falhar, apenas logamos, mas não paramos o fluxo principal
        print(f"AVISO: Falha ao sincronizar usuário {user_id}: {e}")



def call_db_service(endpoint, params=None):
    try:
        response = requests.get(f"{DB_SERVICE_URL}/{endpoint}/", params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {'error': f'Erro de comunicação com o serviço de banco de dados: {e}'}
    except Exception as e:
        return {'error': f'Erro inesperado: {e}'}

@shared_task(name='list_departments_task')
def list_departments_task(user_data):
    ensure_user_exists(user_data)
    user_role = user_data.get('tipo_vinculo')
    user_id = user_data.get('id')
    
    if user_role == 'Servidor':
        return call_db_service('departments')
    else:
        return call_db_service('departments', params={'user_id': user_id})

@shared_task(name='list_rooms_task')
def list_rooms_task(user_data, department_pk):
    ensure_user_exists(user_data)
    user_role = user_data.get('tipo_vinculo')
    user_id = user_data.get('id')
    
    params = {'department_pk': department_pk}
    if user_role != 'Servidor':
        params['user_id'] = user_id
        
    return call_db_service('rooms', params=params)

@shared_task(name='list_iots_task')
def list_iots_task(user_data, room_pk):
    # A lógica de permissão de acesso à sala agora é feita pela query no db_service
    # Aqui apenas repassamos a chamada
    return call_db_service('iots', params={'room_pk': room_pk})