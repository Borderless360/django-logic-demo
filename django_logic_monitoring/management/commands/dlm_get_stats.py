import json

from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import StatStore


class Command(BaseCommand):
    help = "Show collected execution-time statistics"

    def handle(self, *args, **options):
        stats = StatStore.get_all()
        if not stats:
            self.stdout.write("No stats collected")
            return

        self.stdout.write(f"Stats: {len(stats)}")
        for s in sorted(stats, key=lambda x: (x["process"], x["action"], x["step_type"], x["step_name"])):
            last_exec = json.loads(s.get("last_exec", "[]"))
            exec_str = ", ".join(f"{e:.3f}s" for e in last_exec[-5:])
            self.stdout.write(
                f"  {s['process']}.{s['action']} "
                f"{s['step_type']}:{s['step_name']} "
                f"limit={float(s['time_limit']):.3f}s "
                f"runs={len(last_exec)} [{exec_str}]"
            )
