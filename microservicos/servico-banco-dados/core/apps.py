# servico-banco-dados/core/apps.py
from django.apps import AppConfig
import sys

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        if 'makemigrations' in sys.argv or 'migrate' in sys.argv:
            return

        try:
            from .models import IOT
            count = IOT.objects.update(status=False)
        except Exception as e:
            print(f"Erro ao tentar atualizar status do IOTs na inicialização: {e}")