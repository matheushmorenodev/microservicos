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
#class UserPermissionRoomAdmin(admin.ModelAdmin):
 #   list_display = ('user', 'room')   # mostra essas colunas na listagem
 #   search_fields = ('user__id', 'room__name')  # adiciona busca
 #   list_filter = ('room',)  # filtro lateral por sala

# @admin.register(ServidorViewLog)
# class ServidorViewLogAdmin(admin.ModelAdmin):
#     list_display = ('user', 'room')
#     list_filter = ('room', 'user')
#     search_fields = ('user__id', 'room__name')