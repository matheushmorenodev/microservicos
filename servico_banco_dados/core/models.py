from django.db import models

# Create your models here.
from django.db import models
from django.utils.translation import gettext_lazy as _

class ActorUser(models.Model):
    class Role(models.TextChoices):
        ALUNO = 'Aluno', _('Aluno')
        SERVIDOR = 'Servidor', _('Servidor')
        PRESTADOR_SERVICO = 'Prestador Servico', _('Prestador de Serviço')
        ADMIN = 'Admin', _('Admin')

    user_id = models.PositiveIntegerField(primary_key=True, help_text="ID do serviço de autenticação")
    username = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ALUNO, db_index=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.name

class Room(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='rooms')
    def __str__(self):
        return f"{self.name} - {self.department.name}"

class IOT(models.Model):
    name = models.CharField(max_length=100)
    status = models.BooleanField(default=False)
    room = models.ForeignKey(Room, on_delete=models.RESTRICT, related_name='iots')
    def __str__(self):
        status_display = "Conectado" if self.status else "Aguardando Conexão"
        return f'{self.name} ({self.room.name})'

class UserPermissionRoom(models.Model):
    user = models.ForeignKey(ActorUser, on_delete=models.CASCADE)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('user', 'room')

    def __str__(self):
        return f"{self.user.username} -> {self.room.name}"