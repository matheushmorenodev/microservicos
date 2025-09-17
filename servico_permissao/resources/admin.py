from django.contrib import admin

# Register your models here.
from .models import Room, Department, IOT, UserPermissionRoom
from .models import ServidorViewLog

# Registrar os modelos no admin
admin.site.register(Room)
admin.site.register(Department)
admin.site.register(IOT)
admin.site.register(UserPermissionRoom)
admin.site.register(ServidorViewLog)
