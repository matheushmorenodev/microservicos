# core/serializers.py
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .services import SUAPService

class UserLoginSerializer(serializers.Serializer):
    """
    Serializer para validar as credenciais do usuário e gerar os tokens JWT.
    """
    username = serializers.CharField(max_length=150, write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    # Campos que serão retornados na resposta
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        # 1. Autenticar no SUAP usando o serviço
        suap_token = SUAPService.authenticate(username, password)
        
        # 2. Obter dados do usuário
        user_data = SUAPService.get_user_data(suap_token)
        
        # 3. Gerar tokens JWT customizados
        refresh = self.get_token(user_data)

        validated_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        return validated_data

    @classmethod
    def get_token(cls, user_data: dict) -> RefreshToken:
        """Cria um RefreshToken com os dados do usuário no payload."""
        refresh = RefreshToken()
        
        # Adiciona os dados do usuário ao payload de ambos os tokens
        refresh['id'] = user_data.get('id')
        refresh['username'] = user_data.get('matricula') 
        refresh['nome_usual'] = user_data.get('nome_usual')
        refresh['tipo_vinculo'] = user_data.get('tipo_vinculo')
        refresh['url_foto_75x100'] = user_data.get('url_foto_75x100')
        refresh['url_foto_150x200'] = user_data.get('url_foto_150x200')
        
        return refresh

class UserProfileSerializer(serializers.Serializer):
    """Serializer para exibir os dados do perfil do usuário (do token)."""
    id = serializers.IntegerField()
    username = serializers.CharField()
    nome_usual = serializers.CharField()
    tipo_vinculo = serializers.CharField()
    url_foto_75x100 = serializers.URLField()
    url_foto_150x200 = serializers.URLField()