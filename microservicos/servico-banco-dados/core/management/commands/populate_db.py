import random
from django.core.management.base import BaseCommand
from core.models import Department, Room, IOT, ActorUser, UserPermissionRoom

class Command(BaseCommand):
    help = 'Popula o banco de dados com dados de teste para a Guarita (Com Responsáveis)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=== INICIANDO LIMPEZA ==='))
        
        # 1. Limpa tudo (Importante apagar Permissões antes de Users/Rooms)
        UserPermissionRoom.objects.all().delete()
        IOT.objects.all().delete()
        Room.objects.all().delete()
        Department.objects.all().delete()
        ActorUser.objects.all().delete()
        
        self.stdout.write(self.style.WARNING('Dados antigos apagados.'))

        # 2. Cria Usuários (Responsáveis)
        self.stdout.write(self.style.SUCCESS('Criando Usuários...'))
        
        # Lista de nomes fictícios para aparecer na Dashboard
        users_data = [
            ("Douglas Castilho", "Servidor"),
            ("Thiago Caproni", "Servidor"),
            ("Melquisedeque Silva", "Aluno"),
            ("Ana Souza", "Prestador Servico"),
            ("Carlos Oliveira", "Admin"),
            ("Fernanda Lima", "Aluno"),
            ("Roberto Santos", "Servidor")
        ]
        
        created_users = []
        user_id_counter = 1000 # Começa em 1000 para não conflitar com IDs reais baixos
        
        for name, role in users_data:
            user = ActorUser.objects.create(
                user_id=user_id_counter,
                username=name, # Usando o nome completo no username para facilitar a exibição
                role=role
            )
            created_users.append(user)
            user_id_counter += 1

        # 3. Estrutura de Salas
        structure = {
            "Bloco A - Administrativo": [
                "Recepção", "Secretaria", "Diretoria", "Sala de Reuniões", "TI Central"
            ],
            "Bloco B - Salas de Aula": [
                "Sala 101", "Sala 102", "Sala 103", "Auditório"
            ],
            "Bloco C - Laboratórios": [
                "Lab Info 01", "Lab Info 02", "Lab Hardware", "Lab Química", "Robótica"
            ],
            "Área Externa": [
                "Portão Principal", "Portão Ginásio"
            ]
        }

        total_iots = 0
        
        self.stdout.write(self.style.SUCCESS('Criando Salas, IoTs e Vinculando Responsáveis...'))

        # 4. Loop de Criação e Vínculo
        for dept_name, rooms_list in structure.items():
            dept_obj = Department.objects.create(name=dept_name)
            
            for room_name in rooms_list:
                # Cria Sala
                room_obj = Room.objects.create(name=room_name, department=dept_obj)
                
                # Cria IoT (Nome alterado para ESP32)
                iot_name = f"ESP32 - {room_name}"
                
                # Sorteia se está Online ou Offline para dar realismo (80% chance de online)
                is_online = random.random() > 0.2 
                
                IOT.objects.create(
                    name=iot_name,
                    room=room_obj,
                    status=True # Vamos forçar TRUE para você ver todos na dashboard agora
                )
                total_iots += 1
                
                # VINCULAR RESPONSÁVEIS
                # Escolhe aleatoriamente de 1 a 3 usuários para serem donos desta sala
                responsibles_for_room = random.sample(created_users, k=random.randint(1, 3))
                
                for user in responsibles_for_room:
                    UserPermissionRoom.objects.create(user=user, room=room_obj)

        self.stdout.write(self.style.SUCCESS(f'✅ SUCESSO TOTAL!'))
        self.stdout.write(self.style.SUCCESS(f' - {len(users_data)} Usuários criados'))
        self.stdout.write(self.style.SUCCESS(f' - {len(structure)} Departamentos'))
        self.stdout.write(self.style.SUCCESS(f' - {total_iots} Portas (ESP32) criadas'))
        self.stdout.write(self.style.SUCCESS(f' - Permissões distribuídas aleatoriamente.'))