# servico-banco-dados/db_project/wsgi.py
"""
WSGI config for db_project project.
"""
print("--- EXECUTANDO WSGI.PY VERSÃO MAIS RECENTE ---") # NOSSA MENSAGEM DE TESTE

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'db_project.settings')
application = get_wsgi_application()