import jwt
from django.conf import settings
from rest_framework import exceptions

def get_user_info_from_token(request):
    """
    Decodifica o token JWT lendo-o diretamente do cookie 'access_token'.
    """
    # MUDANÇA CRÍTICA: Lendo o token do cookie em vez do header 'Authorization'
    token = request.COOKIES.get('access_token')

    if not token:
        # Se o cookie não estiver presente, negamos o acesso.
        return None

    try:
        # A lógica de decodificação permanece a mesma
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise exceptions.AuthenticationFailed('Token expirado')
    except jwt.InvalidTokenError:
        raise exceptions.AuthenticationFailed('Token inválido')
    except Exception:
        raise exceptions.AuthenticationFailed('Erro de autenticação')