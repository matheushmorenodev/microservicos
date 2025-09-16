from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Department, Room, IOT
from .serializers import DepartmentSerializer, RoomSerializer, IOTSerializer, ServidorViewLog
from .permissions import IsServidorOuPrestador, IsAlunoComPermissao
from rest_framework.response import Response

class ListDepartamentsWithAccessAPIView(generics.ListAPIView):
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]  # garante que precisa estar logado

    def get_queryset(self):
        user = self.request.user

        if user.role in (
            "Servidor",
            "Prestador Servico",
        ):
            return Department.objects.all()

        if user.role == "Aluno":
            return Department.objects.filter(
                room__userpermissionroom__user=user
            ).distinct()

        return Department.objects.none()  # segurança extra


class ListRoomsWithAccessAPIView(generics.ListAPIView):
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role in (
            "Servidor",
            "Prestador Servico",
        ):
            return Room.objects.all()

        if user.role == "Aluno":
            return Room.objects.filter(userpermissionroom__user=user)

        return Room.objects.none()



class ListIOTWithAccessAPIView(generics.ListAPIView):
    serializer_class = IOTSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.role in ("Servidor", "Prestador Servico"):
            return IOT.objects.all()

        if user.role == "Aluno":
            return IOT.objects.filter(room__userpermissionroom__user=user)

        return IOT.objects.none()

    def list(self, request, *args, **kwargs):
        """
        Sobrescreve a resposta para incluir o campo 'servidor' no topo.
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        user = request.user
        servidor_has_access = False

        if user.role == "Servidor":
            # Verifica se o servidor tem algum vínculo em ServidorViewLog
            servidor_has_access = ServidorViewLog.objects.filter(user=user).exists()

        return Response({
            "results": serializer.data,
            "owner": servidor_has_access
        })