# core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.db import transaction
from .views import (
    ActorUserViewSet,
    DepartmentViewSet,
    RoomViewSet,
    IOTViewSet,
    UserPermissionRoomViewSet,
    LogEntryViewSet,
    IOTRegistrationViewSet
)

router = DefaultRouter()
router.register(r'users', ActorUserViewSet, basename='actoruser')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'iots', IOTViewSet, basename='iot')
router.register(r'user-permissions', UserPermissionRoomViewSet)
router.register(r'logs', LogEntryViewSet)
# Registro da nova viewset
router.register(r'iot-registration', IOTRegistrationViewSet, basename='iot-registration')

urlpatterns = [
    path('', include(router.urls)),
]