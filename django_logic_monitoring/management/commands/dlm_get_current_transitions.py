from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import TransitionStore


class Command(BaseCommand):
    help = "Return active transitions with states"

    LIMIT = 30

    def handle(self, *args, **options):
        transitions = TransitionStore.get_all()
        if not transitions:
            self.stdout.write("No active transitions")
            return

        total = len(transitions)
        transitions.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
        shown = transitions[: self.LIMIT]

        self.stdout.write(self.style.WARNING(f"Total: {total} (showing last {len(shown)})\n"))
        for tr in shown:
            self.stdout.write(
                f"{tr['id']} {tr['timestamp']} {tr['process']}.{tr.get('action', '')} "
                f"{tr['model_name']}#{tr['object_id']} "
                f"{tr['step_type']}:{tr['step_name']} "
                f"({tr['step_n']}/{tr['steps']}) "
            )
