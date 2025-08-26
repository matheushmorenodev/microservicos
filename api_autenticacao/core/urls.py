from django.urls import path
from .views import LoginView, PerfilView, CustomTokenRefreshView
from rest_framework_simplejwt.views import TokenVerifyView

urlpatterns = [
    path('login/', LoginView.as_view()),
    path('perfil/', PerfilView.as_view()),
    path('token/verify/', TokenVerifyView.as_view()),
    path('token/refresh/', CustomTokenRefreshView.as_view()),
]
