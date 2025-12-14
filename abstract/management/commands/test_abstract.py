from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from abstract.models import B, B_STATES

User = get_user_model()


class Command(BaseCommand):
    help = 'e2e test for abstract logic.'

    def handle(self, *args, **kwargs):
        user, _ = User.objects.get_or_create(
            username='user',
            defaults={'is_staff': False, 'is_superuser': False}
        )
        staff_user, _ = User.objects.get_or_create(
            username='staff_user',
            defaults={'is_staff': True, 'is_superuser': False}
        )
        
        print(f"Abstract logic test")

        # test next transition with no permissions
        b = B.objects.create(status=B_STATES.B0)
        b.process.B0_B1(user=staff_user)