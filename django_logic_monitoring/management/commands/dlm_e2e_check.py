import json

from django.core.management.base import BaseCommand

from core.redis import redis_client
from django_logic_monitoring.actions import fetch_logs, detect_anomaly
from django_logic_monitoring.storage import (
    AnomalyStore,
    StatStore,
    TransitionStore,
)

DLM_KEYS_PATTERN = "dlm:*"


class Command(BaseCommand):
    help = (
        "E2E check for django_logic_monitoring: "
        "process all ClickHouse logs, show results"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear DLM Redis state before processing",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_dlm_keys()

        self.stdout.write("\n--- fetch_logs ---")
        fetch_logs()

        self._show_transitions()
        self._show_stats()

        self.stdout.write("\n--- detect_anomaly ---")
        anomalies = detect_anomaly()

        self._show_anomalies(anomalies)
        self.stdout.write("")

    def _clear_dlm_keys(self):
        keys = redis_client.keys(DLM_KEYS_PATTERN)
        if keys:
            redis_client.delete(*keys)
            self.stdout.write(f"Cleared {len(keys)} dlm:* keys from Redis")
        else:
            self.stdout.write("No dlm:* keys to clear")

    def _show_transitions(self):
        transitions = TransitionStore.get_all()
        self.stdout.write(f"\n--- Active transitions: {len(transitions)} ---")
        for tr in transitions:
            completed = tr.get("is_completed") == "1"
            self.stdout.write(
                f"  [{tr['id'][:8]}] {tr['process']}.{tr.get('action', '')} "
                f"{tr['model_name']}#{tr['object_id']} "
                f"step={tr['step_type']}:{tr['step_name']} "
                f"({tr['step_n']}/{tr['steps']}) "
                f"completed={completed}"
            )

    def _show_stats(self):
        stats = StatStore.get_all()
        self.stdout.write(f"\n--- Stats: {len(stats)} ---")
        for s in sorted(stats, key=lambda x: (x["process"], x["action"], x["step_type"], x["step_name"])):
            last_exec = json.loads(s.get("last_exec", "[]"))
            exec_str = ", ".join(f"{e:.3f}s" for e in last_exec[-5:])
            self.stdout.write(
                f"  {s['process']}.{s['action']} "
                f"{s['step_type']}:{s['step_name']} "
                f"limit={float(s['time_limit']):.3f}s "
                f"runs={len(last_exec)} [{exec_str}]"
            )

    def _show_anomalies(self, new_anomalies):
        all_anomalies = AnomalyStore.get_all()
        self.stdout.write(f"\n--- Anomalies: {len(all_anomalies)} (new: {len(new_anomalies)}) ---")
        for a in new_anomalies:
            self.stdout.write(
                f"  [{a['anomaly_id']}] tr={a['tr_id'][:8]} "
                f"{a['process']}.{a['action']} "
                f"{a['step_type']}:{a['step_name']} "
                f"exec={a['current_exec']:.1f}s limit={a['time_limit']:.1f}s"
            )
