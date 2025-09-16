from django.db import models

class ActorUser(models.Model):
    class ActorUserRolesChoices(models.TextChoices):
        ALUNO = 'Aluno'
        SERVIDOR = 'Servidor'
        PRESTADOR_SERVICO = 'Prestador Servico'


    user_id = models.IntegerField(unique=True) # ID do usuário vindo do Auth Service
    username = models.CharField(max_length=150, unique=True) # Username para referência
    role = models.CharField(
        max_length=20,
        choices=ActorUserRolesChoices.choices,
        default=ActorUserRolesChoices.ALUNO
    )
    @property
    def is_authenticated(self):
        """
        Necessário para o Django/DRF reconhecer esse objeto como usuário válido.
        Sempre retorna True, porque se chegamos aqui o token já foi validado.
        """
        return True

#Tercerizado
class PrestadorServico(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Prestador Serviço - ID: {self.user_id}'
#ALUNO
class Aluno(models.Model):
    user_id = models.IntegerField(unique=True)
    def __str__(self):
        return f'Aluno - ID: {self.user_id}'
    
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