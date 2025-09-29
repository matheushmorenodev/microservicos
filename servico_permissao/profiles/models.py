# models.py
from django.db import models
from django.utils.translation import gettext_lazy as _

class ActorUser(models.Model):
    """
    Representa um usuário sincronizado a partir de um serviço de autenticação externo.

    Este modelo atua como uma cópia local ("ator") dos dados essenciais do usuário
    para estabelecer relações e permissões dentro deste microserviço, sem
    armazenar credenciais sensíveis.
    """

    class Role(models.TextChoices):
        """Define os papéis (níveis de acesso) que um usuário pode ter no sistema."""
        ALUNO = 'ALUNO', _('Aluno')
        SERVIDOR = 'SERVIDOR', _('Servidor')
        PRESTADOR_SERVICO = 'PRESTADOR_SERVICO', _('Prestador de Serviço')
        ADMIN = 'ADMIN', _('Admin')
        # Adicionar novos papéis aqui é simples e centralizado.

    # O user_id do serviço de autenticação é a chave primária natural neste contexto.
    # Isso evita a criação de uma coluna 'id' extra e otimiza as buscas.
    user_id = models.PositiveIntegerField(
        primary_key=True,
        help_text=_("ID único do usuário vindo do serviço de autenticação.")
    )

    username = models.CharField(
        _("nome de usuário"),
        max_length=150,
        unique=True,
        help_text=_("Nome de usuário para referência e exibição.")
    )

    role = models.CharField(
        _("papel"),
        max_length=20,
        choices=Role.choices,
        default=Role.ALUNO,
        db_index=True, # Adicionar um índice melhora a performance de filtros por 'role'.
        help_text=_("Define o nível de permissão do usuário no sistema.")
    )

    # A propriedade is_authenticated é uma excelente forma de integrar
    # este modelo customizado com os sistemas de permissão do Django/DRF.
    @property
    def is_authenticated(self) -> bool:
        """
        Sempre retorna True, pois a existência deste objeto implica que o
        usuário foi validado via token pelo serviço de autenticação.
        """
        return True

    def __str__(self):
        # Uma representação em string mais informativa é útil no Django Admin.
        return f"{self.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = _("Usuário Ator")
        verbose_name_plural = _("Usuários Atores")
