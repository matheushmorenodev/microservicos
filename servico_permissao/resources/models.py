# models.py
from django.db import models
from profiles.models import ActorUser
from .constants import UserRoles # ✨ Importando as constantes

class Department(models.Model):
    # 'id' é adicionado automaticamente pelo Django
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100)
    # on_delete=PROTECT evita que um departamento seja deletado se ainda tiver salas
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='rooms')
    
    def __str__(self):
        return f"{self.name} - {self.department.name}"

class IOT(models.Model):
    name = models.CharField(max_length=100)
    status = models.BooleanField(default=False)
    # related_name='iots' para facilitar queries reversas: room.iots.all()
    room = models.ForeignKey(Room, on_delete=models.RESTRICT, related_name='iots')

    def __str__(self):
        status_display = "Conectado" if self.status else "Aguardando Conexão"
        return f'{self.name} ({self.room.name}) - {status_display}'
    
class UserPermissionRoom(models.Model):
    user = models.ForeignKey(ActorUser, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    
    class Meta:
        # Garante que não haja permissões duplicadas
        unique_together = ('user', 'room')

    def __str__(self):
        return f"{self.user.username} -> {self.room.name}"

class ServidorViewLog(models.Model):
    user = models.ForeignKey(
        ActorUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': UserRoles.SERVIDOR}, # ✨ Usando constante
    )
    room = models.ForeignKey(Room, on_delete=models.RESTRICT, related_name='log_permissions')

    def __str__(self):
        return f"{self.user.username} pode ver logs de {self.room.name}"