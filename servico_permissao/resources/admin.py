from django.contrib import admin

# Register your models here.
from .models import Room, Department, IOT

# Registrar os modelos no admin
admin.site.register(Room)
admin.site.register(Department)
admin.site.register(IOT)