# servico-autenticacao/core/urls.py
from django.urls import path
from .views import LoginAPIView, ProfileAPIView, CustomTokenRefreshView
from rest_framework_simplejwt.views import TokenVerifyView

urlpatterns = [
    path('login/', LoginAPIView.as_view(), name='auth_login'),
    path('profile/', ProfileAPIView.as_view(), name='auth_profile'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
]