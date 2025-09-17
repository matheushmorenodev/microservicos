# serializers.py
from rest_framework import serializers
from .models import Department, Room, IOT, ServidorViewLog
from .constants import UserRoles

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

class RoomSerializer(serializers.ModelSerializer):
    # 'department' é o nome correto do campo no modelo Room
    department = DepartmentSerializer(read_only=True)
    
    class Meta:
        model = Room
        fields = ['id', 'name', 'department']

class IOTSerializer(serializers.ModelSerializer):
    room = serializers.StringRelatedField()
    
    class Meta:
        model = IOT
        
        fields = ['id', 'name', 'status', 'room']