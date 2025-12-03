# servico-banco-dados/core/views.py
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.db import transaction
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
    filterset_fields = ['name', 'status', 'room'] 

    def get_queryset(self):
        queryset = IOT.objects.all()
        
        # Pega os parâmetros
        room_pk = self.request.query_params.get('room_pk')
        user_id = self.request.query_params.get('user_id')
        name = self.request.query_params.get('name', None)
        status = self.request.query_params.get('status', None)
        
        # --- AQUI ESTÁ A LÓGICA DO ROOM_PK ---
        if room_pk is not None:
            # Filtra onde o campo 'room' é igual ao ID passado
            queryset = queryset.filter(room=room_pk)
        # -------------------------------------

        if name is not None:
            queryset = queryset.filter(name__icontains=name)
        
        if user_id is not None:
            queryset = queryset.filter(room__userpermissionroom__user_id=user_id).distinct()

        if status is not None:
            if str(status).lower() == 'true':
                status = True
            elif str(status).lower() == 'false':
                status = False
            queryset = queryset.filter(status=status)        
        
        return queryset

class UserPermissionRoomViewSet(viewsets.ModelViewSet):
    queryset = UserPermissionRoom.objects.all()
    serializer_class = UserPermissionRoomSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserPermissionRoomFilter

class LogEntryViewSet(viewsets.ModelViewSet):
    queryset = LogEntry.objects.all()
    serializer_class = LogEntrySerializer

class IOTConnectionViewSet(viewsets.ViewSet): 
    """
    ViewSet customizada para gerenciar o status de conexão de um IOT.
    Fornece as ações 'connect' e 'disconnect'.
    """
    # permission_classes = [IsAuthenticated] 

    @action(detail=False, methods=['post'], url_path='connect')
    def connect(self, request):
        """
        Recebe: { "name_iot", "name_room", "name_department" }
        
        Se o IOT existir, marca status=True.
        Se não existir, cria a hierarquia (Dept, Room, IOT) e marca status=True.
        """
        data = request.data
        name_iot = data.get('name_iot')
        name_room = data.get('name_room')
        name_department = data.get('name_department')

        print("Dados recebidos para conectar IOT:", data)

        if not all([name_iot, name_room, name_department]):
            return Response(
                {"error": "Os campos 'name_iot', 'name_room', e 'name_department' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            iot = IOT.objects.get(name=name_iot)
            iot.status = True
            iot.save(update_fields=['status'])
            serializer = IOTSerializer(iot)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IOT.DoesNotExist:
            try:
                with transaction.atomic():
                    department, _ = Department.objects.get_or_create(name=name_department)
                    room, _ = Room.objects.get_or_create(name=name_room, department=department)
                    iot = IOT.objects.create(name=name_iot, room=room, status=True)
                    serializer = IOTSerializer(iot)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response(
                    {"error": f"Erro ao criar hierarquia: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
    
    @action(detail=False, methods=['post'], url_path='disconnect')
    def disconnect(self, request):
        """
        Recebe: { "name_iot" }
        e atualiza o status desse IOT para False (desconectado).
        """
        data = request.data
        name_iot = data.get('name_iot')

        if not name_iot:
            return Response(
                {"error": "O campo 'name_iot' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            iot = IOT.objects.get(name=name_iot)
            iot.status = False
            iot.save(update_fields=['status'])
            serializer = IOTSerializer(iot)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IOT.DoesNotExist:
            return Response(
                {"error": f"IOT com o nome '{name_iot}' não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data
        name_iot = data.get('name_iot')

        # 1. Validação
        if not name_iot:
            return Response(
                {"error": "O campo 'name_iot' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 2. Tenta encontrar o IOT
            iot = IOT.objects.get(name=name_iot)
            
            # 3. Se existir, atualiza o status para False e retorna
            iot.status = False
            iot.save(update_fields=['status'])
            
            serializer = IOTSerializer(iot)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except IOT.DoesNotExist:
            # 4. Se não existir, retorna erro
            return Response(
                {"error": f"IOT com o nome '{name_iot}' não encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )