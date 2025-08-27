from rest_framework import serializers
from .models import Department, Room, IOT
from profiles.models import Coordinator, Admin, Common

from . import models


# --- Serializers para LEITURA (Read) ---

class CoordinatorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coordinator
        fields = ['id', 'user_id'] # Adicionado ID para facilitar a referência

class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['user_id']

class CommonProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Common
        fields = ['user_id']

#Serializers dos locais
#Departamento
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']

#Sala
class RoomSerializer(serializers.ModelSerializer):
    departament = DepartmentSerializer(read_only=True)
    class Meta:
        model = Room
        fields = ['id', 'name', 'departament']

#IOT
class IOTSerializer(serializers.ModelSerializer):
    room = serializers.StringRelatedField()  # mostra __str__ do Room
    status = serializers.CharField()         # pode restringir validação se quiser

    class Meta:
        model = IOT
        fields = ['id', 'room', 'status']
