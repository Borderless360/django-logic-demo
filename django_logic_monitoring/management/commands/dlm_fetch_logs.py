from django.core.management.base import BaseCommand

from django_logic_monitoring.actions import fetch_logs


class Command(BaseCommand):
    help = "Run fetch_logs action of the monitoring process"

    def handle(self, *args, **options):
        fetch_logs()
