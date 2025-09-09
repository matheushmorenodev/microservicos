import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

import jwt
from django.conf import settings

SUAP_TOKEN_URL = 'https://suap.ifsuldeminas.edu.br/api/token/pair'
SUAP_USER_URL = 'https://suap.ifsuldeminas.edu.br/api/rh/meus-dados/'

class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        data={'username': username,'password': password}

        suap_resp = requests.post(SUAP_TOKEN_URL, json=data)

        if suap_resp.status_code != 200:
            return Response({'detail': 'Credenciais inválidas'}, status=status.HTTP_401_UNAUTHORIZED)

        suap_token = suap_resp.json().get('access')

        user_resp = requests.get(SUAP_USER_URL, headers={
            'Authorization': f'Bearer {suap_token}'
        })

        if user_resp.status_code != 200:
            return Response({'detail': 'Erro ao obter dados do SUAP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        user = user_resp.json()

        # Criar token JWT próprio
        refresh = RefreshToken()
        refresh['id'] = user.get('id')
        refresh['username'] = username
        refresh['nome_usual'] = user.get('nome_usual')
        #refresh['tipo_vinculo'] = 'Prestador Servico'
        refresh['tipo_vinculo'] = user.get('tipo_vinculo')
        refresh['url_foto_75x100'] = user.get('url_foto_75x100')
        refresh['url_foto_150x200'] = user.get('url_foto_150x200')

        access = refresh.access_token
        access['id'] = user.get('id')
        access['username'] = username
        access['nome_usual'] = user.get('nome_usual')
        #access['tipo_vinculo'] = 'Prestador Servico'
        access['tipo_vinculo'] = user.get('tipo_vinculo')
        access['url_foto_75x100'] = user.get('url_foto_75x100')
        access['url_foto_150x200'] = user.get('url_foto_150x200')

        return Response({
            'access': str(access),
            'refresh': str(refresh),
            #'user': decoded,
        })

class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'detail': 'Refresh token inválido ou expirado'}, status=401)

        access = serializer.validated_data['access']

        # Retorna access token novo + o mesmo refresh token
        return Response({
            'access': access,
            'refresh': request.data['refresh'],
            #'user': decoded,
        })

class PerfilView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'nome_usual': user.nome_usual,
            'tipo_vinculo': user.tipo_vinculo,
            'url_foto_75x100': user.url_foto_75x100,
            'url_foto_150x200': user.url_foto_150x200,
        })
