from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from autofixer.monitor import MonitoringService


class Command(BaseCommand):
    help = "Run autofixer monitor loop in foreground"

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=5)

    def handle(self, *args, **options):
        interval = int(options["interval"])
        monitor = MonitoringService()
        self.stdout.write(self.style.SUCCESS(f"Autofixer started. Poll interval={interval}s"))
        while True:
            result = monitor.tick()
            self.stdout.write(str(result))
            time.sleep(interval)

