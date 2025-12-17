from django.core.management.base import BaseCommand
from abstract.e2e import test_basic


class Command(BaseCommand):
    help = 'e2e test for abstractlogic.'

    def handle(self, *args, **kwargs):
        test_basic.test_basic_transition()
