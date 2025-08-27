# core/views.py

from django.db.models import Q
from rest_framework import generics

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
        user = self.request.user
        print(f"Listando departamentos para o usuário: {user.nome_usual} (ID: {user.id})")

        # A lógica agora é apenas sobre o que retornar.
        # Se você reativar as permissões, use `user.id`.
        # Exemplo: return Department.objects.filter(coordinators__user_id=user.id)
        return Department.objects.all()


class ListRoomsWithAccessAPIView(generics.ListAPIView):
    """
    Lista as Salas de um determinado Departamento.
    """
    serializer_class = RoomSerializer

    def get_queryset(self):
        # O usuário já está autenticado e disponível.
        user = self.request.user
        departamento_id = self.kwargs.get('departamento') # Pega o parâmetro da URL

        # A lógica da view fica limpa e focada no seu objetivo.
        return Room.objects.filter(department_id=departamento_id)


class ListIOTWithAccessAPIView(generics.ListAPIView):
    """
    Lista os dispositivos IOT de uma determinada Sala.
    """
    serializer_class = IOTSerializer

    def get_queryset(self):
        # Acesso direto e seguro às informações do usuário.
        user = self.request.user
        sala_id = self.kwargs.get('sala') # Pega o parâmetro da URL

        return IOT.objects.filter(room_id=sala_id)