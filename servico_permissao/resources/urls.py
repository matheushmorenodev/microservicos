from django.urls import path
from .views import (
        
)


urlpatterns = [
    
    path('listar-todos-departamentos/', ViewALLDepartamentos.as_view(), name=''),
    path('listar-todas-salas/{departamento}', ListRoomsWithAccessAPIView.as_view(), name='listar_minhas_salas'),
    path('listar-todos-dispositivos/{sala}', ViewALLDepartamentos.as_view(), name=''),
]
