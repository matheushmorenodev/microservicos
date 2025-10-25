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

class IOTRegistrationViewSet(viewsets.ViewSet):
    """
    ViewSet customizada para registrar ou atualizar um IOT.
    Fornece uma ação 'register'.
    """
    
    # IMPORTANTE: Adicione as permissões aqui quando estiver pronto
    # permission_classes = [IsAuthenticated] 

    @action(detail=False, methods=['post'], url_path='register')
    def register_iot(self, request):
        """
        Recebe: { "name_iot", "name_room", "name_departament" }
        e cria/atualiza o IOT e sua hierarquia.
        """
        data = request.data
        name_iot = data.get('name_iot')
        name_room = data.get('name_room')
        name_departament = data.get('name_departament')

        # 1. Validação simples da entrada
        if not all([name_iot, name_room, name_departament]):
            return Response(
                {"error": "Os campos 'name_iot', 'name_room', e 'name_departament' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # 2. Tenta encontrar o IOT
            iot = IOT.objects.get(name=name_iot)
            
            # 3. Se existir, atualiza o status e retorna
            iot.status = True
            iot.save(update_fields=['status'])
            
            serializer = IOTSerializer(iot)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except IOT.DoesNotExist:
            # 4. Se não existir, cria a hierarquia de forma atômica
            try:
                with transaction.atomic():
                    # 4a. Garante que o Departamento exista
                    department, _ = Department.objects.get_or_create(
                        name=name_departament
                    )
                    
                    # 4b. Garante que a Sala exista NAQUELE departamento
                    room, _ = Room.objects.get_or_create(
                        name=name_room,
                        department=department
                    )
                    
                    # 4c. Cria o IOT com status True (1)
                    iot = IOT.objects.create(
                        name=name_iot,
                        room=room,
                        status=True
                    )
                    
                    serializer = IOTSerializer(iot)
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                # Captura erros durante a transação (ex: falha de constraint)
                return Response(
                    {"error": f"Erro ao criar hierarquia: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )