from rest_framework import serializers
from .models import ActorUser, Department, Room, UserPermissionRoom, IOT, LogEntry

class ActorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActorUser
        fields = ['user_id', 'username', 'role']

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

class RoomSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    class Meta:
        model = Room
        fields = ['id', 'name', 'department']

class IOTSerializer(serializers.ModelSerializer):
    room = RoomSerializer(read_only=True)
    class Meta:
        model = IOT
        fields = ['id', 'name', 'status', 'room']

class UserPermissionRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermissionRoom
        fields = ['id', 'user', 'room']
        
#Log
class LogEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LogEntry
        fields = ['id', 'timestamp', 'service_name', 'level', 'message', 'correlation_id']