from django.db import models

class UserRoles(models.TextChoices):
    SERVIDOR = "Servidor", "Servidor"
    PRESTADOR_SERVICO = "Prestador Servico", "Prestador de Serviço"
    ALUNO = "Aluno", "Aluno"
    ADMIN = "Admin", "Admin"