from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from locker.models import Lock, LOCK_STATES

User = get_user_model()


class Command(BaseCommand):
    help = 'e2e test for locker logic.'

    def handle(self, *args, **kwargs):
        user, _ = User.objects.get_or_create(
            username='user',
            defaults={'is_staff': False, 'is_superuser': False}
        )
        staff_user, _ = User.objects.get_or_create(
            username='staff_user',
            defaults={'is_staff': True, 'is_superuser': False}
        )
        
        lock = Lock.objects.create(status=LOCK_STATES.open)
        lock.process.lock(user=user)
        print(f"Lock status: {lock.status}")
        lock.process.unlock(user=staff_user)
        print(f"Lock status: {lock.status}")
        # TODO: fix maintain transition
        # lock.process.maintain(user=staff_user)
        print(f"Lock status: {lock.status}")
