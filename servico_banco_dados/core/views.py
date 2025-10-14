from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.views import APIView
from .models import LogEntry
from .serializers import LogEntrySerializer
from django_filters.rest_framework import DjangoFilterBackend
from .filters import UserPermissionRoomFilter 
from .models import ActorUser, Department, Room, UserPermissionRoom, IOT
from .serializers import (
    ActorUserSerializer,
    DepartmentSerializer,
    RoomSerializer,
    UserPermissionRoomSerializer,
    IOTSerializer
)

class ActorUserViewSet(viewsets.ModelViewSet):
    queryset = ActorUser.objects.all()
    serializer_class = ActorUserSerializer
    lookup_field = 'user_id'
    def update(self, request, *args, **kwargs):
        """
        Sobrescreve o método PUT para funcionar como 'get_or_create'.
        """
        # Tenta buscar o usuário pelo 'lookup_field' (user_id)
        try:
            instance = self.get_object()
            # Se encontrar, atualiza (comportamento padrão)
            return super().update(request, *args, **kwargs)
        except:
            # Se não encontrar (Http404), cria um novo
            return self.create(request, *args, **kwargs)

class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    def get_queryset(self):
        queryset = Department.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id is not None:
            return queryset.filter(rooms__userpermissionroom__user_id=user_id).distinct()
        return queryset

class RoomViewSet(viewsets.ModelViewSet):
    serializer_class = RoomSerializer
    def get_queryset(self):
        queryset = Room.objects.all()
        department_pk = self.request.query_params.get('department_pk')
        user_id = self.request.query_params.get('user_id')
        if department_pk is not None:
            queryset = queryset.filter(department_id=department_pk)
        if user_id is not None:
            queryset = queryset.filter(userpermissionroom__user_id=user_id)
        return queryset.distinct()

class IOTViewSet(viewsets.ModelViewSet):
    serializer_class = IOTSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']
    def get_queryset(self):
        queryset = IOT.objects.all()
        room_pk = self.request.query_params.get('room_pk')
        if room_pk is not None:
            queryset = queryset.filter(room_id=room_pk)
        return queryset

class UserPermissionRoomViewSet(viewsets.ModelViewSet):
    queryset = UserPermissionRoom.objects.all()
    serializer_class = UserPermissionRoomSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserPermissionRoomFilter
    
class LogEntryViewSet(viewsets.ModelViewSet):
    queryset = LogEntry.objects.all()
    serializer_class = LogEntrySerializer
    

