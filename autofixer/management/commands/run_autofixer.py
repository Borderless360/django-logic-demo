"""Run autofixer monitor in a loop (Mon-1: singleton process)."""

import logging
import signal
import sys

from django.core.management.base import BaseCommand

from autofixer.monitor import Monitor

logger = logging.getLogger("autofixer")


class Command(BaseCommand):
    help = "Run autofixer monitor (polls logs, detects anomalies, runs actions)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=float,
            default=5,
            help="Poll interval in seconds (default: 5, Mon-2: near-realtime)",
        )

    def handle(self, *args, **options):
        interval = options["interval"]
        monitor = Monitor()
        self.stdout.write(f"Autofixer running (interval={interval}s). Ctrl+C to stop.")
        self.stdout.write("")

        def on_sigterm(signum, frame):
            logger.info("Autofixer received SIGTERM, shutting down")
            sys.exit(0)

        signal.signal(signal.SIGTERM, on_sigterm)

        import time

        try:
            while True:
                monitor.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("\nStopped.")
