from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import AnomalyStore, TransitionStore


class Command(BaseCommand):
    help = "Show detected execution-time anomalies"

    def handle(self, *args, **options):
        anomalies = AnomalyStore.get_all()
        if not anomalies:
            self.stdout.write("No anomalies")
            return

        anomalies.sort(key=lambda a: a.get("timestamp", ""), reverse=True)

        rows = []
        for a in anomalies:
            rows.append((
                a["id"],
                a["tr_id"],
                f"{float(a['current_exec']):.1f}s",
                a.get("timestamp", "")[:19],
            ))

        exec_w = max(len("Exec"), *(len(r[2]) for r in rows))

        self.stdout.write(self.style.WARNING(f"Anomalies: {len(anomalies)}\n"))
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"{'ID':>7}  {'Transition':<36}  {'Exec':>{exec_w}}  Detected at"
        ))
        for r in rows:
            self.stdout.write(
                f"{r[0]:>7}  {r[1]:<36}  {r[2]:>{exec_w}}  {r[3]}"
            )

        self.stdout.write("")
        for a in anomalies:
            tr = TransitionStore.get(a["tr_id"])
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"Anomaly #{a['id']}  transition {a['tr_id']}"
            ))
            if not tr:
                self.stdout.write("  Transition not found (completed or removed)\n")
                continue

            self.stdout.write(
                f"  Object:  {tr.get('model_name', '?')}"
                f" pk={tr.get('object_id', '?')}"
                f" field={tr.get('field_name', '?')}"
            )
            self.stdout.write(
                f"  Process: {tr.get('process', '?')}"
                f"  action={tr.get('action', '?')}"
            )
            step_n = tr.get("step_n", "?")
            steps = tr.get("steps", "?")
            self.stdout.write(
                f"  Stuck:   {tr.get('step_type', '?')}"
                f" \"{tr.get('step_name', '?')}\""
                f"  (step {step_n}/{steps})"
            )
            self.stdout.write(
                f"  Since:   {tr.get('timestamp', '?')[:19]}\n"
            )
