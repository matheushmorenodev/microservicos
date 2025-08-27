import jwt
from django.conf import settings
from rest_framework import exceptions

def get_user_info_from_token(request):
    """
    Decodifica o token JWT lendo-o diretamente do cabeçalho 'Authorization' (Bearer <token>).
    Retorna o payload decodificado ou lança exceções caso o token seja inválido ou expirado.
    """
    # Recupera o token do cabeçalho Authorization
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        raise exceptions.AuthenticationFailed('Cabeçalho Authorization não encontrado')

    # O cabeçalho deve ser no formato "Bearer <token>"
    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise exceptions.AuthenticationFailed('Formato do token inválido')

    token = parts[1]

    try:
        # Decodifica o token com a chave secreta
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,  # A chave secreta para validar o token
            algorithms=["HS256"]  # Algoritmo usado na assinatura do JWT
        )
        return payload  # Retorna o payload decodificado

    except jwt.ExpiredSignatureError:
        # Caso o token tenha expirado
        raise exceptions.AuthenticationFailed('Token expirado')

    except jwt.InvalidTokenError:
        # Caso o token seja inválido
        raise exceptions.AuthenticationFailed('Token inválido')

    except Exception:
        # Para qualquer outro erro
        raise exceptions.AuthenticationFailed('Erro ao processar o token')