"""Show active transitions (UA-1: user can view at any time)."""

from django.core.management.base import BaseCommand

from autofixer.tracker import TransitionTracker


class Command(BaseCommand):
    help = "Show active django-logic transitions"

    def handle(self, *args, **options):
        tracker = TransitionTracker()
        active = tracker.get_active()

        if not active:
            self.stdout.write("No active transitions.")
            return

        self.stdout.write(f"Active transitions ({len(active)}):")
        self.stdout.write("")
        for t in active:
            self.stdout.write(
                f"  {t.tr_id}  {t.process_class}.{t.action_name}  "
                f"instance={t.instance_key}  root={t.root_id}  started={t.started_at}"
            )
