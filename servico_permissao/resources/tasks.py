from celery import shared_task
from .models import Department
from .serializers import DepartmentSerializer
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