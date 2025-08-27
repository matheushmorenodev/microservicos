from django.urls import path
from .views import (
    ListRoomsWithAccessAPIView,
    ListDepartamentsWithAccessAPIView,
    ListIOTWithAccessAPIView,
)


urlpatterns = [
    
    path('listar-todos-departamentos/', ListDepartamentsWithAccessAPIView.as_view(), name='listar_meus_departamentos'),
    path('listar-todas-salas/<int:departamento>/', ListRoomsWithAccessAPIView.as_view(), name='listar_minhas_salas'),
    path('listar-todos-dispositivos/<int:sala>/', ListIOTWithAccessAPIView.as_view(), name='listar_meus_dispositivos'),
]
