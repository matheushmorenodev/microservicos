from rest_framework import serializers
from .models import ActorUser, Department, Room, UserPermissionRoom, IOT

class ActorUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActorUser
        fields = ['user_id', 'username', 'role']

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'name', 'department']

class IOTSerializer(serializers.ModelSerializer):
    class Meta:
        model = IOT
        fields = ['id', 'name', 'status', 'room']

class UserPermissionRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPermissionRoom
        fields = ['id', 'user', 'room']