# core/authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
import jwt
from django.conf import settings
# from profiles.models import ActorUser
from .constants import UserRoles # ✨ Usando constantes

class JWTAuthentication(BaseAuthentication):
    """
    Valida um token JWT, busca ou sincroniza o usuário local (ActorUser)
    e o anexa ao objeto 'request'.
    """
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None # Nenhuma tentativa de autenticação

        try:
            # Validação do formato 'Bearer <token>'
            prefix, token = auth_header.split()
            if prefix.lower() != "bearer":
                raise exceptions.AuthenticationFailed("O cabeçalho Authorization deve começar com 'Bearer'")
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed("Cabeçalho Authorization mal formatado.")

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token expirado.")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Token inválido.")

        user_id = payload.get("id")
        username = payload.get("username")
        
        if not user_id or not username:
            raise exceptions.AuthenticationFailed("Payload do token incompleto.")

        # # Usa update_or_create para simplificar e garantir atomicidade
        # user, created = ActorUser.objects.update_or_create(
        #     user_id=user_id,
        #     defaults={
        #         "username": username,
        #         "role": payload.get("tipo_vinculo", UserRoles.ALUNO), # Usando constante
        #     },
        # )

        return (user, None) # Sucesso na autenticação