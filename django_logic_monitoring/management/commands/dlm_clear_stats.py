from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import StatStore


class Command(BaseCommand):
    help = "Clear all collected execution-time statistics"

    def handle(self, *args, **options):
        count = StatStore.clear_all()
        self.stdout.write(f"Cleared {count} stat entries")
