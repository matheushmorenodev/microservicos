# servico-autenticacao/suap_auth/urls.py
from django.urls import path, include

urlpatterns = [
    path('api/', include('core.urls')),
]
