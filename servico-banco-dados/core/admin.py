# servico-banco-dados/core/admin.py
from django.contrib import admin
from .models import ActorUser, Department, Room, IOT, UserPermissionRoom, LogEntry

# Este comando diz ao Django para mostrar cada modelo no painel de administração
admin.site.register(ActorUser)
admin.site.register(Department)
admin.site.register(Room)
admin.site.register(IOT)
admin.site.register(UserPermissionRoom)
admin.site.register(LogEntry)