# core/authentication.py
from dataclasses import dataclass
from rest_framework_simplejwt.authentication import JWTAuthentication

@dataclass
class AuthenticatedUser:
    """
    Classe de dados para representar um usuário autenticado stateless.
    Usa dataclass para um código mais limpo e legível.
    """
    id: int
    username: str
    nome_usual: str
    tipo_vinculo: str
    url_foto_75x100: str
    url_foto_150x200: str
    
    @property
    def is_authenticated(self) -> bool:
        return True

class CustomJWTAuthentication(JWTAuthentication):
    """
    Autenticação JWT que retorna um objeto de usuário stateless 
    em vez de um modelo de usuário do Django.
    """
    def get_user(self, validated_token):
        # Mapeia o payload do token para o nosso dataclass
        return AuthenticatedUser(
            id=validated_token.get('id'),
            username=validated_token.get('username'),
            nome_usual=validated_token.get('nome_usual'),
            tipo_vinculo=validated_token.get('tipo_vinculo'),
            url_foto_75x100=validated_token.get('url_foto_75x100'),
            url_foto_150x200=validated_token.get('url_foto_150x200'),
        )