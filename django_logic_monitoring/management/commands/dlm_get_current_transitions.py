from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import TransitionStore


class Command(BaseCommand):
    help = "Return active transitions with states"

    def handle(self, *args, **options):
        transitions = TransitionStore.get_all()
        if not transitions:
            self.stdout.write("No active transitions")
            return

        for tr in transitions:
            completed = tr.get("is_completed") == "1"
            self.stdout.write(
                f"[{tr['id'][:8]}] {tr['process']}.{tr.get('action', '')} "
                f"{tr['model_name']}#{tr['object_id']} "
                f"step: {tr['step_type']}:{tr['step_name']} "
                f"({tr['step_n']}/{tr['steps']}) "
                f"completed: {completed} "
                f"ts: {tr['timestamp']}"
            )
