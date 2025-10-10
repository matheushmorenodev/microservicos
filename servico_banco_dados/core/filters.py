from django_filters import rest_framework as filters
from .models import UserPermissionRoom

class UserPermissionRoomFilter(filters.FilterSet):
    iot_name = filters.CharFilter(method='filter_by_iot_name')

    class Meta:
        model = UserPermissionRoom
        fields = ['user', 'room']

    def filter_by_iot_name(self, queryset, name, value):
        # Esta consulta filtra as permissões de sala, procurando
        # em qual sala o IOT com o nome 'value' está localizado.
        return queryset.filter(room__iots__name=value)