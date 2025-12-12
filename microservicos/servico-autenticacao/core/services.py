# servico-autenticacao/core/services.py
import requests
from django.conf import settings
from rest_framework import exceptions

class SUAPService:
    """
    Serviço para encapsular a comunicação com a API do SUAP.
    """
    
    @staticmethod
    def authenticate(username: str, password: str) -> str:
        """
        Autentica o usuário no SUAP e retorna o token de acesso.
        Levanta uma exceção AuthenticationFailed em caso de falha.
        """
        try:
            response = requests.post(
                settings.SUAP_TOKEN_URL, 
                json={'username': username, 'password': password},
                timeout=5 # Boa prática: adicionar timeout
            )
            response.raise_for_status() # Levanta exceção para status 4xx/5xx
            return response.json().get('access')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise exceptions.AuthenticationFailed('Credenciais SUAP inválidas.')
            raise exceptions.APIException(f"Erro de comunicação com o SUAP: {e}")
        except requests.exceptions.RequestException as e:
            raise exceptions.APIException(f"Erro de conexão com o SUAP: {e}")

    @staticmethod
    def get_user_data(suap_token: str) -> dict:
        """
        Busca os dados do usuário no SUAP usando o token de acesso.
        Levanta uma exceção APIException em caso de falha.
        """
        try:
            response = requests.get(
                settings.SUAP_USER_DATA_URL,
                headers={'Authorization': f'Bearer {suap_token}'},
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise exceptions.APIException(f"Erro ao obter dados do usuário no SUAP: {e}")