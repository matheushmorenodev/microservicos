# core/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
import jwt
from django.conf import settings
from profiles.models import ActorUser

class ValidateJWTAuthentication(BaseAuthentication):
    """
    Valida token JWT vindo de outro serviço (auth-service) e cria/sincroniza o ActorUser.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None  # DRF considera como não autenticado

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise exceptions.AuthenticationFailed("Cabeçalho Authorization inválido")

        token = parts[1]

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token expirado")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Token inválido")

        user_id = payload.get("id")
        username = payload.get("username")
        tipo_vinculo = payload.get("tipo_vinculo", ActorUser.ActorUserRolesChoices.ALUNO)

        if not user_id or not username:
            raise exceptions.AuthenticationFailed("Token sem informações de usuário suficientes")

        # Cria ou sincroniza usuário no banco
        actor_user, created = ActorUser.objects.get_or_create(
            user_id=user_id,
            defaults={"username": username, "tipo_vinculo": tipo_vinculo},
        )

        if not created:
            changed = False
            if actor_user.username != username:
                actor_user.username = username
                changed = True
            if actor_user.role != tipo_vinculo:
                actor_user.role = tipo_vinculo
                changed = True
            if changed:
                actor_user.save()

        return (actor_user, None)
