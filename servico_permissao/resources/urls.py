# urls.py
from django.urls import path
from .views import (
    ListDepartmentsAPIView,
    ListRoomsAPIView,
    ListIOTsAPIView,
)

#app_name = 'core' # Boa prática: adicionar um namespace

urlpatterns = [
    path('departments/', ListDepartmentsAPIView.as_view(), name='department-list'),
    path('departments/<int:department_pk>/rooms/', ListRoomsAPIView.as_view(), name='room-list'),
    path('rooms/<int:room_pk>/iots/', ListIOTsAPIView.as_view(), name='iot-list'),
]