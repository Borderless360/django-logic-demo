from django.core.management.base import BaseCommand

from django_logic_monitoring.actions import detect_anomaly


class Command(BaseCommand):
    help = "Run detect_anomaly action of the monitoring process"

    def handle(self, *args, **options):
        detect_anomaly()
