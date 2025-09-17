# permissions.py
from rest_framework.permissions import BasePermission
from .constants import UserRoles # ✨ Usando constantes

class HasDepartmentAccess(BasePermission):
    """Permite acesso se o usuário for Servidor/Prestador ou um Aluno com permissão."""
    def has_permission(self, request, view):
        # Apenas estar autenticado já é o suficiente, o filtro do queryset fará o resto.
        return request.user and request.user.is_authenticated

class HasRoomAccess(BasePermission):
    """Verifica se o usuário tem permissão para acessar salas de um departamento específico."""
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.role in (UserRoles.SERVIDOR, UserRoles.PRESTADOR_SERVICO):
            return True

        # Para alunos, verificamos se ele tem permissão em alguma sala DAQUELE departamento
        department_pk = view.kwargs.get('department_pk')
        return user.userpermissionroom_set.filter(room__department_id=department_pk).exists()

class HasIOTAccess(BasePermission):
    """Verifica se o usuário tem permissão para acessar IOTs de uma sala específica."""
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.role in (UserRoles.SERVIDOR, UserRoles.PRESTADOR_SERVICO):
            return True

        # Para alunos, verificamos se ele tem permissão NAQUELA sala
        room_pk = view.kwargs.get('room_pk')
        return user.userpermissionroom_set.filter(room_id=room_pk).exists()