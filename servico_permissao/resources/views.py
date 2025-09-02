
from django.db.models import Q
from rest_framework import generics

from rest_framework.exceptions import PermissionDenied

from resources.utils import get_or_create_user_from_token
from profiles.models import ActorUser

from .models import IOT, Department, Room
from .serializers import DepartmentSerializer, IOTSerializer, RoomSerializer

# Não precisamos mais de 'get_or_create_user_from_token' ou de uma classe base customizada aqui,
# pois a configuração foi feita globalmente no settings.py.

# --- Views de LEITURA ---

class ListDepartamentsWithAccessAPIView(generics.ListAPIView):
    """
    Lista todos os Departamentos. O acesso a esta view já é protegido
    pela configuração global.
    """
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        user = get_or_create_user_from_token(self.request)
        print(user.role)
        if user.role == ActorUser.ActorUserRolesChoices.SERVIDOR or user.role == ActorUser.ActorUserRolesChoices.PRESTADOR_SERVICO :
            return Department.objects.all()
        elif user.role == ActorUser.ActorUserRolesChoices.ALUNO:
            return Department.objects.all()
        else:
            raise PermissionDenied("Usuario sem permissao.")


class ListRoomsWithAccessAPIView(generics.ListAPIView):
    """
    Lista as Salas de um determinado Departamento.
    """
    serializer_class = RoomSerializer

    def get_queryset(self):
        user = get_or_create_user_from_token(self.request)
        if user.role == ActorUser.ActorUserRolesChoices.SERVIDOR or user.role == ActorUser.ActorUserRolesChoices.PRESTADOR_SERVICO :
            return Room.objects.all()
        elif user.role == ActorUser.ActorUserRolesChoices.ALUNO:
            return Room.objects.all()
        else:
            raise PermissionDenied("Usuario sem permissao.")


class ListIOTWithAccessAPIView(generics.ListAPIView):
    """
    Lista os dispositivos IOT de uma determinada Sala.
    """
    serializer_class = IOTSerializer

    def get_queryset(self):
        user = get_or_create_user_from_token(self.request)
        if user.role == ActorUser.ActorUserRolesChoices.SERVIDOR or user.role == ActorUser.ActorUserRolesChoices.PRESTADOR_SERVICO :
            return IOT.objects.all()
        elif user.role == ActorUser.ActorUserRolesChoices.ALUNO:
            return IOT.objects.all()
        else:
            raise PermissionDenied("Usuario sem permissao.")