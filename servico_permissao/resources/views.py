from django.shortcuts import render




# --- Views de LEITURA ---
#se necessario para guarita
# class ListAllRoomsAPIView(generics.ListAPIView):
#     queryset = Room.objects.all()
#     serializer_class = RoomSerializer
#     permission_classes = [HasRole]
#     #allowed_roles = ['padrao','administrador','servidor','coordenador']
    
class ListALLRoomsAPIView(generics.ListAPIView):
    queryset = Room.objects.all()
    
class ListRoomsWithAccessAPIView(generics.ListAPIView):
    serializer_class = RoomSerializer
    def get_queryset(self):
        user_info = get_user_info_from_token(self.request)
        if not user_info:
            return Room.objects.none('Usuario nao encontrado')
        
        user_id = user_info.get('user_id')
        if not user_id:
            return Room.objects.none('Usuario nao encontrado')
        return Room.objects.filter(
            Q(admins__user_id=user_id) |
            Q(users__user_id=user_id) |
            Q(department__coordinators__user_id=user_id) |
            Q(special_coordinators__user_id=user_id)
        ).distinct()    
        
        
        
        
# from django.db.models import Q

# # Supondo que você já tenha o `user_id` e o `user` carregado
# user = User.objects.get(id=user_id)

# # Lógica baseada no tipo de usuário
# if user.role == 'aluno':
#     # Se for aluno, ele pode ter permissões específicas
#     rooms = Room.objects.filter(
#         Q(users__user_id=user_id) |
#         Q(department__coordinators__user_id=user_id)  # Exemplo de permissões para aluno
#     ).distinct()

# elif user.role == 'servidor':
#     # Se for servidor, ele pode ter permissões mais amplas, por exemplo, admins
#     rooms = Room.objects.filter(
#         Q(admins__user_id=user_id) |
#         Q(users__user_id=user_id) |
#         Q(department__coordinators__user_id=user_id) |
#         Q(special_coordinators__user_id=user_id)  # Exemplo de permissões para servidor
#     ).distinct()
        
    