from celery import shared_task
from .models import Department, Room, IOT
from .serializers import DepartmentSerializer, RoomSerializer, IOTSerializer
from profiles.models import ActorUser
from .constants import UserRoles
import json

@shared_task(name='list_departments_task')
def list_departments_task(user_data):
    """
    Executa a lógica de negócio que antes estava na View.
    Recebe os dados do usuário (payload do token) e retorna os departamentos.
    """
    try:
        # Recria um objeto 'user' simples para usar na lógica de filtragem
        user_role = user_data.get('tipo_vinculo')
        user_id = user_data.get('id')

        queryset = Department.objects.none()

        if user_role in (UserRoles.SERVIDOR, UserRoles.PRESTADOR_SERVICO):
            queryset = Department.objects.all()
        elif user_role == UserRoles.ALUNO:
            queryset = Department.objects.filter(rooms__userpermissionroom__user_id=user_id).distinct()

        serializer = DepartmentSerializer(queryset, many=True)

        # Celery funciona melhor com tipos de dados primitivos (dict, list, etc)
        return serializer.data

    except Exception as e:
        # É importante tratar exceções e retornar um erro claro
        return {'error': str(e)}
# --- NOVA TAREFA PARA LISTAR SALAS ---
@shared_task(name='list_rooms_task')
def list_rooms_task(user_data, department_pk):
    try:
        user_role = user_data.get('tipo_vinculo')
        user_id = user_data.get('id')
        queryset = Room.objects.none()
        
        # Filtra primeiro pelo departamento solicitado
        base_query = Room.objects.filter(department_id=department_pk)

        if user_role in (UserRoles.SERVIDOR, UserRoles.ADMIN):
            queryset = base_query.all()
        elif user_role == UserRoles.ALUNO:
            # Da base de salas do departamento, filtra apenas as que o usuário tem permissão
            queryset = base_query.filter(userpermissionroom__user_id=user_id).distinct()

        serializer = RoomSerializer(queryset, many=True)
        return serializer.data
    except Exception as e:
        return {'error': str(e), 'service': 'permission_worker'}

# --- NOVA TAREFA PARA LISTAR IOTS ---
@shared_task(name='list_iots_task')
def list_iots_task(user_data, room_pk):
    try:
        user_role = user_data.get('tipo_vinculo')
        user_id = user_data.get('id')
        
        # Passo de segurança: antes de listar os IOTs, verifica se o usuário tem acesso à sala
        tem_acesso = False
        if user_role in (UserRoles.SERVIDOR, UserRoles.ADMIN):
            tem_acesso = Room.objects.filter(pk=room_pk).exists()
        elif user_role == UserRoles.ALUNO:
            tem_acesso = Room.objects.filter(pk=room_pk, userpermissionroom__user_id=user_id).exists()

        if not tem_acesso:
            return {'error': 'Acesso negado a esta sala.'}

        # Se tem acesso, lista os IOTs da sala
        queryset = IOT.objects.filter(room_id=room_pk)
        serializer = IOTSerializer(queryset, many=True)
        return serializer.data
    except Exception as e:
        return {'error': str(e), 'service': 'permission_worker'}