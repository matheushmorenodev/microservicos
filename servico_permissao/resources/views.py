# core/views.py

from django.db.models import Q
from rest_framework import generics

from rest_framework.exceptions import PermissionDenied
from servico_permissao.resources.utils import get_user_info_from_token

from .models import IOT, Department, Room
from .serializers import DepartmentSerializer, IOTSerializer, RoomSerializer

# Não precisamos mais de 'get_user_info_from_token' ou de uma classe base customizada aqui,
# pois a configuração foi feita globalmente no settings.py.

# --- Views de LEITURA ---

class ListDepartamentsWithAccessAPIView(generics.ListAPIView):
    """
    Lista todos os Departamentos. O acesso a esta view já é protegido
    pela configuração global.
    """
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        # O DRF já autenticou o usuário. O objeto `StatelessUser` está em `self.request.user`.
        # user = self.request.user
        payload = get_user_info_from_token(self.request)
        role = payload.get("role")
        if role != "servidor":
            raise PermissionDenied("Apenas servidores podem listar departamentos.")
        #print(f"Listando departamentos para o usuário: {user.nome_usual} (ID: {user.id})")

        return Department.objects.all()


class ListRoomsWithAccessAPIView(generics.ListAPIView):
    """
    Lista as Salas de um determinado Departamento.
    """
    serializer_class = RoomSerializer

    def get_queryset(self):
        # O usuário já está autenticado e disponível.
        #user = self.request.user
        #departamento_id = self.kwargs.get('departamento') # Pega o parâmetro da URL
        payload = get_user_info_from_token(self.request)
        role = payload.get("role")
        departamento_id = self.kwargs.get("departamento")
        if role in ["servidor", "padrao"]:
            # A lógica da view fica limpa e focada no seu objetivo.
            return Room.objects.filter(department_id=departamento_id)
        raise PermissionDenied("Você não tem permissão para listar salas.")


class ListIOTWithAccessAPIView(generics.ListAPIView):
    """
    Lista os dispositivos IOT de uma determinada Sala.
    """
    serializer_class = IOTSerializer

    def get_queryset(self):
        # Acesso direto e seguro às informações do usuário.
        #user = self.request.user
        #sala_id = self.kwargs.get('sala') # Pega o parâmetro da URL
        payload = get_user_info_from_token(self.request)
        role = payload.get("role")
        sala_id = self.kwargs.get("sala")
        
        if role == "servidor":
            return IOT.objects.filter(room_id=sala_id)
        raise PermissionDenied("Apenas servidores podem listar dispositivos.")