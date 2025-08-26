from django.db import models

class ActorUser(models.Model):
    class ActorUserRolesChoices(models.TextChoices):
        USUARIO_PADRAO = 'padrao'
        COORDENADOR = 'coordenador'
        ADMINISTRADOR = 'administrador'
        SERVIDOR = 'servidor'


    user_id = models.IntegerField(unique=True) # ID do usuário vindo do Auth Service
    username = models.CharField(max_length=150, unique=True) # Username para referência
    role = models.CharField(
        max_length=20,
        choices=ActorUserRolesChoices.choices,
        default=ActorUserRolesChoices.USUARIO_PADRAO
    )

#COORDENADOR DE SALA
class Coordinator(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Coordenador - ID: {self.user_id}'
#ALUNO
class Common(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Comum - ID: {self.user_id}'
    
#SERVIDORES
class Service(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Servidor - ID: {self.user_id}'
    
#PERFIL que faremos para nti
class Admin(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Admin - ID: {self.user_id}'