from django.core.management.base import BaseCommand

from django_logic_monitoring.storage import AnomalyStore, AnomalyType, TransitionStore

ANOMALY_TYPE_NAMES = {str(t.value): t.name for t in AnomalyType}


class Command(BaseCommand):
    help = "Show detected execution-time anomalies"

    def add_arguments(self, parser):
        type_choices = [t.name.lower() for t in AnomalyType]
        parser.add_argument(
            "--type",
            choices=type_choices,
            help=f"Filter by anomaly type: {', '.join(type_choices)}",
        )

    def handle(self, *args, **options):
        anomalies = AnomalyStore.get_all()

        if options["type"]:
            filter_value = str(AnomalyType[options["type"].upper()].value)
            anomalies = [a for a in anomalies if a.get("type") == filter_value]

        if not anomalies:
            self.stdout.write("No anomalies")
            return

        anomalies.sort(key=lambda a: a.get("timestamp", ""), reverse=True)

        # rows = []
        # for a in anomalies:
        #     type_name = ANOMALY_TYPE_NAMES.get(a.get("type", ""), "?")
        #     rows.append((
        #         a["id"],
        #         a["tr_id"],
        #         type_name,
        #         f"{a.get('process', '?')}.{a.get('action', '?')}",
        #         f"{a.get('step_type', '?')}:{a.get('step_name', '?')}",
        #         a.get("timestamp", "")[:19],
        #     ))

        # self.stdout.write(self.style.WARNING(f"Anomalies: {len(anomalies)}\n"))
        # self.stdout.write(self.style.MIGRATE_HEADING(
        #     f"{'ID':>7}  {'Transition':<36}  {'Type':<16}  {'Process':<24}  {'Step':<30}  Detected at"
        # ))
        # for r in rows:
        #     self.stdout.write(
        #         f"{r[0]:>7}  {r[1]:<36}  {r[2]:<16}  {r[3]:<24}  {r[4]:<30}  {r[5]}"
        #     )

        self.stdout.write("")
        for a in anomalies:
            type_name = ANOMALY_TYPE_NAMES.get(a.get("type", ""), "?")
            tr = TransitionStore.get(a["tr_id"])
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"Anomaly #{a['id']}  [{type_name}] {a['tr_id']}  {tr.get('timestamp', '?')[:19]}"
            ))
            if not tr:
                self.stdout.write("  Transition not found (completed or removed)\n")
                continue

            self.stdout.write(
                f"  {tr.get('model_name', '?')}"
                f" {tr.get('object_id', '?')}"
                f" {tr.get('field_name', '?')}"
            )
            step_n = tr.get("step_n", "?")
            steps = tr.get("steps", "?")
            self.stdout.write(
                f"  {a.get('process', '?')}.{a.get('action', '?')}"
                f"  {a.get('step_type', '?')} \"{a.get('step_name', '?')}\""
                f"  (step {step_n}/{steps})"
            )
