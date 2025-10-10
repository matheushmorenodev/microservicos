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
    
class MqttClientConnectedView(APIView):
    """
    Webhook para ser chamado pelo broker MQTT quando um dispositivo se conecta.
    Ele espera um 'clientid' que corresponda ao campo 'name' de um IOT já cadastrado.
    """
    def post(self, request):
        client_id = request.data.get("clientid")
        if not client_id:
            return Response({"error": "clientid não fornecido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Procura o dispositivo pelo nome (que deve ser único)
            iot_device = IOT.objects.get(name=client_id)
            iot_device.status = True  # Define o status como 'Conectado'
            iot_device.save()
            
            print(f"Dispositivo conectado e status atualizado para ONLINE: {client_id}")
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        except IOT.DoesNotExist:
            print(f"AVISO: Tentativa de conexão de dispositivo não cadastrado: {client_id}")
            return Response({"error": f"Dispositivo com nome '{client_id}' não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"ERRO no webhook de conexão MQTT: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MqttClientDisconnectedView(APIView):
    """
    Webhook para ser chamado pelo broker MQTT quando um dispositivo se desconecta.
    """
    def post(self, request):
        client_id = request.data.get("clientid")
        if not client_id:
            return Response({"error": "clientid não fornecido"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Apenas atualiza o status se o dispositivo existir
            updated_count = IOT.objects.filter(name=client_id).update(status=False)
            
            if updated_count > 0:
                print(f"Dispositivo desconectado e status atualizado para OFFLINE: {client_id}")
            else:
                print(f"AVISO: Tentativa de desconexão de dispositivo não cadastrado: {client_id}")

            return Response({"status": "ok"}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"ERRO no webhook de desconexão MQTT: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)