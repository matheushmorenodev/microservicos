# servico-autenticacao/core/views.py
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from .serializers import UserLoginSerializer, UserProfileSerializer

class LoginAPIView(APIView):
    """
    Recebe credenciais (username, password), autentica no SUAP 
    e retorna tokens JWT de acesso e refresh.
    """
    permission_classes = [permissions.AllowAny] # Não requer autenticação

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

class ProfileAPIView(APIView):
    """
    Retorna os dados do perfil do usuário logado, extraídos do token JWT.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # request.user agora é uma instância de AuthenticatedUser
        serializer = UserProfileSerializer(instance=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class CustomTokenRefreshView(TokenRefreshView):
    """
    Endpoint para renovar um token de acesso usando um token de refresh.
    A implementação padrão já é segura e suficiente.
    A customização anterior não é necessária.
    """
    pass # A implementação padrão já lida com tudo.