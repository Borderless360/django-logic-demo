from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from autofixer.monitor import MonitoringService


class Command(BaseCommand):
    help = "Show current autofixer status"

    def handle(self, *args, **options):
        status = MonitoringService().get_status()
        self.stdout.write(json.dumps(status, indent=2, sort_keys=True))

