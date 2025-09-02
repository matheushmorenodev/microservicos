import jwt
from django.conf import settings
from rest_framework import exceptions
from profiles.models import ActorUser


def get_or_create_user_from_token(request):
    """
    Decodifica o token JWT, sincroniza/cria o ActorUser no banco
    e retorna o objeto ActorUser.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise exceptions.AuthenticationFailed('Cabeçalho Authorization não encontrado')

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise exceptions.AuthenticationFailed('Formato do token inválido')

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Token expirado')
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed('Token inválido')
    except Exception:
        raise exceptions.AuthenticationFailed('Erro ao processar o token')

    # Aqui assumo que o payload tem pelo menos: id (user_id), username, role
    user_id = payload.get("id")
    username = payload.get("username")
    role = payload.get("tipo_vinculo", ActorUser.ActorUserRolesChoices.ALUNO)

    if not user_id or not username:
        raise exceptions.AuthenticationFailed("Token sem informações de usuário suficientes")

    # Busca ou cria o ActorUser
    actor_user, created = ActorUser.objects.get_or_create(
        user_id=user_id,
        defaults={
            "username": username,
            "tipo_vinculo": role
        }
    )

    # Se já existia, atualiza os dados (caso a role ou username mudem no auth-service)
    if not created:
        if actor_user.username != username or actor_user.role != role:
            actor_user.username = username
            actor_user.role = role
            actor_user.save()

    return actor_user
