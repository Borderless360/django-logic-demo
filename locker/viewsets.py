from rest_framework import viewsets

from demo.locker.models import Lock
from demo.locker.serializers import LockerSerializer


class LockerViewSet(viewsets.ModelViewSet):
    queryset = Lock.objects.all()
    serializer_class = LockerSerializer
