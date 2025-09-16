from rest_framework import serializers
from .models import Department, Room, IOT
from profiles.models import PrestadorServico, Admin, Aluno
from .models import ServidorViewLog
from . import models


# --- Serializers para LEITURA (Read) ---

class PrestadorServicoProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrestadorServico
        fields = ['id', 'user_id'] # Adicionado ID para facilitar a referência

class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['user_id']

class AlunoProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aluno
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
    room = serializers.StringRelatedField()

    class Meta:
        model = IOT
        fields = '__all__'


class ServidorViewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServidorViewLog
        fields = '__all__'