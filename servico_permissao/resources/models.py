from django.db import models
#from profiles.models import Common, Coordinator, Service, Admin 


class Department(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return f"{self.name}"

class Room(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE) 
    
    def __str__(self):
        return f"{self.name} - {self.department}"

class IOT(models.Model):
    status = models.BooleanField(default=False) # True = Conectado, False = Aguardando Conexão
    name = models.CharField(max_length=100)
    room = models.ForeignKey(Room, related_name='iot_objects', on_delete=models.RESTRICT)
    def __str__(self):
        return f'{self.room} - {"Conectado" if self.status else "Aguardando Conexão"}'