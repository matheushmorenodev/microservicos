from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *
from .views import (MqttClientConnectedView,
                    MqttClientDisconnectedView)

router = DefaultRouter()
router.register(r'users', ActorUserViewSet, basename='actoruser')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'rooms', RoomViewSet, basename='room')
router.register(r'iots', IOTViewSet, basename='iot')
router.register(r'user-permissions', UserPermissionRoomViewSet)
router.register(r'logs', LogEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('mqtt/connected/', MqttClientConnectedView.as_view()),
    path('mqtt/disconnected/', MqttClientDisconnectedView.as_view()),
]