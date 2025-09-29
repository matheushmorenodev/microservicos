# views.py
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department, Room, IOT, ServidorViewLog
from .serializers import DepartmentSerializer, RoomSerializer, IOTSerializer
from .permissions import HasDepartmentAccess, HasRoomAccess, HasIOTAccess 
from .constants import UserRoles 


class AccessFilteredQuerysetMixin:
    """
    Mixin que filtra o queryset com base no papel (role) do usuário.
    - Servidores e Prestadores de Serviço veem tudo.
    - Alunos veem apenas o que têm permissão.
    """
    def get_queryset(self):
        user = self.request.user
        model = self.serializer_class.Meta.model

        # Servidores e Prestadores veem tudo
        if user.role in (UserRoles.SERVIDOR, UserRoles.PRESTADOR_SERVICO):
            return model.objects.all()

        # Alunos veem apenas o que têm permissão explícita
        if user.role == UserRoles.ALUNO:
            if model == Department:
                return Department.objects.filter(room__userpermissionroom__user=user).distinct()
            if model in (Room, IOT):
                # Para Room e IOT a lógica de filtro é a mesma
                return model.objects.filter(room__userpermissionroom__user=user)

        return model.objects.none() # Princípio de negação por padrão


# class ListDepartmentsAPIView(AccessFilteredQuerysetMixin, generics.ListAPIView):
#     """Lista os departamentos que o usuário logado tem acesso."""
#     serializer_class = DepartmentSerializer
#     permission_classes = [IsAuthenticated, HasDepartmentAccess] # Permissão mais específica


class ListRoomsAPIView(AccessFilteredQuerysetMixin, generics.ListAPIView):
    """Lista as salas de um departamento que o usuário logado tem acesso."""
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated, HasRoomAccess]

    def get_queryset(self):
        # Filtra primeiro pelo mixin, depois pelo departamento da URL
        queryset = super().get_queryset()
        departamento_id = self.kwargs.get('department_pk')
        return queryset.filter(department_id=departamento_id)


class ListIOTsAPIView(AccessFilteredQuerysetMixin, generics.ListAPIView):
    """Lista os dispositivos IOT de uma sala que o usuário logado tem acesso."""
    serializer_class = IOTSerializer
    permission_classes = [IsAuthenticated, HasIOTAccess]

    def get_queryset(self):
        queryset = super().get_queryset()
        sala_id = self.kwargs.get('room_pk')
        return queryset.filter(room_id=sala_id)

    def list(self, request, *args, **kwargs):
        """
        Sobrescreve a resposta para aninhar a lista de IOTs sob a chave 'data'
        e mover a chave 'owner' para o nível raiz.
        """
        # 1. Obter os dados serializados como antes
        queryset = self.get_queryset()
        # Não precisamos mais do campo 'owner' no IOTSerializer para este formato
        serializer = self.get_serializer(queryset, many=True)
        
        # 2. Calcular o valor de 'owner' uma única vez
        user = request.user
        is_owner = False
        if user.is_authenticated and user.role == UserRoles.SERVIDOR:
            is_owner = ServidorViewLog.objects.filter(user=user).exists()

        # 3. Construir a estrutura de resposta personalizada
        response_data = {
            'data': serializer.data,
            'owner': is_owner
        }
        
        return Response(response_data)