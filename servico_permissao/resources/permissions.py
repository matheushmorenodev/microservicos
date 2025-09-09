from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from profiles.models import ActorUser


class IsServidorOuPrestador(BasePermission):
    """
    Permite acesso apenas a usuários com vínculo de Servidor ou Prestador.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            if request.user.tipo_vinculo in (
                ActorUser.ActorUserRolesChoices.SERVIDOR,
                ActorUser.ActorUserRolesChoices.PRESTADOR_SERVICO,
            ):
                return True
        raise PermissionDenied("Apenas Servidores e Prestadores podem acessar.")


class IsAlunoComPermissao(BasePermission):
    """
    Permite acesso a alunos, mas apenas se eles tiverem permissão em salas/departamentos.
    O filtro real fica no queryset da view.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            if request.user.tipo_vinculo == ActorUser.ActorUserRolesChoices.ALUNO:
                return True
        return False
