"""Management command to show logs with Background Mode SideEffectSingleTask queued."""
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand

from clickhouse.client import client


def _ts_to_ch_literal(ts: datetime) -> str:
    if ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts.strftime("%Y-%m-%d %H:%M:%S") + f".{ts.microsecond // 1000:03d}"


def _tr_id_from_msg(text: str | None) -> str | None:
    if not text:
        return None
    head, sep, tail = text.strip().partition(" ")
    if not sep or not tail:
        return None
    return head


def parse_start_line_msg(
    text: str | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """From a log line containing 'Start', return (Process, Action, Obj, transition_id)."""
    if not text:
        return None, None, None, None
    parts = text.split()
    try:
        i = parts.index("Start")
    except ValueError:
        return None, None, None, None
    if i + 3 >= len(parts):
        return None, None, None, None
    proc, act, obj = parts[i + 1], parts[i + 2], parts[i + 3]
    tid = parts[i + 4] if i + 4 < len(parts) else None
    return proc, act, obj, tid


def parse_executes_transition_msg(
    text: str | None, tr_id: str
) -> tuple[str | None, str | None]:
    """
    Object and Action from:
    "<…> <Object>, process process executes '<Action>' transition from …"
    Uses str.partition / split only (no regex). tr_id locates the tail after which Object is parsed.
    """
    if not text or not tr_id:
        return None, None
    marker = ", process process executes '"
    if marker not in text:
        return None, None
    before, _, after = text.partition(marker)
    pos = before.find(tr_id)
    if pos < 0:
        return None, None
    tail = before[pos + len(tr_id) :].strip()
    if not tail:
        return None, None
    obj = tail.split()[-1]
    action, _, _ = after.partition("' transition from")
    if not action:
        return None, None
    return obj, action


def fetch_start_fields_for_tr_id(
    tr_id: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """ClickHouse: Start or transition line for tr_id; parse Process/Action/Obj/transition_id."""
    tr_esc = tr_id.replace("'", "''")
    query_start = f"""
        SELECT msg
        FROM logs
        WHERE msg LIKE '% Start %'
          AND msg LIKE '%{tr_esc}%'
        ORDER BY _timestamp ASC
        LIMIT 1
    """
    result = client.query(query_start)
    rows = result.result_rows
    if rows:
        (msg,) = rows[0]
        return parse_start_line_msg(msg)

    query_transition = f"""
        SELECT msg
        FROM logs
        WHERE msg LIKE '%transition from%'
          AND msg LIKE '%{tr_esc}%'
        ORDER BY _timestamp ASC
        LIMIT 1
    """
    result = client.query(query_transition)
    rows = result.result_rows
    if not rows:
        return None, None, None, None
    (msg,) = rows[0]
    obj, action = parse_executes_transition_msg(msg, tr_id)
    return None, action, obj, None


# example of log lines (fffab00a… = correlation id in msg; 277855c8… = transition id after Obj on Start):
# 2026-03-20 09:12:48.691 fffab00a-7f1c-4e4a-8820-82381757ddfd │   order-order-state-9623891, process process executes 'generate_labels' transition from fulfilling to fulfilling  
# 2026-03-20 09:12:48.691 fffab00a-7f1c-4e4a-8820-82381757ddfd │   Start OrderProcess generate_labels order-order-state-9623891 277855c8-a956-468f-99b3-3fb0192926de 277855c8-a956-468f-99b3-3fb0192926de
# 2026-03-20 09:12:48.693 fffab00a-7f1c-4e4a-8820-82381757ddfd │   Lock
# 2026-03-20 09:12:48.708 fffab00a-7f1c-4e4a-8820-82381757ddfd │   Background Mode SideEffectSingleTask queued with {'app_label': 'order', 'model_name': 'order', 'instance_id': 9623891, 'process_name': 'process', 'field_name': 'state', 'action_name': 'generate_labels', 'process_class': 'order.business_logic.processes.process.OrderProcess'}


class Command(BaseCommand):
    help = (
        "Check django logic celery transitions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since-days",
            type=float,
            default=14,
            help="Scan logs from this many days ago until now (default: 14).",
        )
        parser.add_argument(
            "--window-hours",
            type=float,
            default=12,
            help="Length of each time window in hours (default: 12).",
        )

    def handle(self, *args, **options):
        pattern = "%Background Mode SideEffectSingleTask queued with%"
        since_days = options["since_days"]
        window_hours = options["window_hours"]
        total_read = 0
        window_idx = 0
        unique_pairs: set[tuple[str | None, str | None]] = set()
        obj_transitions: dict[str, set[tuple[str, str]]] = {}

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        range_end = now_utc
        range_start = range_end - timedelta(days=since_days)
        window_delta = timedelta(hours=window_hours)

        self.stderr.write(
            f"fuckup_check: интервалы по {window_hours} ч, "
            f"диапазон [{_ts_to_ch_literal(range_start)} .. {_ts_to_ch_literal(range_end)}), "
            f"один запрос на окно, ORDER BY _timestamp\n"
        )

        hour_start = range_start
        while hour_start < range_end:
            hour_end = min(hour_start + window_delta, range_end)
            window_idx += 1
            lo = _ts_to_ch_literal(hour_start)
            hi = _ts_to_ch_literal(hour_end)

            query = f"""
                SELECT _timestamp, msg
                FROM logs
                WHERE msg LIKE '{pattern}'
                  AND _timestamp >= toDateTime64('{lo}', 3)
                  AND _timestamp < toDateTime64('{hi}', 3)
                ORDER BY _timestamp
            """
            result = client.query(query)
            rows = result.result_rows
            window_rows = len(rows)
            total_read += window_rows

            for row in rows:
                _, msg = row
                text = msg or ""
                tr_id = _tr_id_from_msg(text)
                proc, action, obj, transition_uid = (
                    fetch_start_fields_for_tr_id(tr_id)
                    if tr_id
                    else (None, None, None, None)
                )
                unique_pairs.add((proc, action))
                trans_key = transition_uid or tr_id
                if obj and action and trans_key:
                    obj_transitions.setdefault(obj, set()).add((trans_key, action))

            self.stderr.write(
                f"fuckup_check: окно #{window_idx} [{lo} .. {hi}) — "
                f"строк в окне: {window_rows}; всего: {total_read}; "
                f"Process|Action: {len(unique_pairs)}; объектов: {len(obj_transitions)}\n"
            )
            hour_start = hour_end

        self.stderr.write(f"fuckup_check: конец диапазона, всего прочитано {total_read}\n")

        self.stdout.write("=== Process | Action (unique) ===")
        for proc, action in sorted(
            unique_pairs,
            key=lambda p: ((p[0] or ""), (p[1] or "")),
        ):
            self.stdout.write(f"{proc or '-'} | {action or '-'}")

        self.stdout.write("")
        self.stdout.write("=== Object -> transitions ===")
        for obj_key in sorted(obj_transitions):
            self.stdout.write(f"{obj_key}:")
            entries = sorted(obj_transitions[obj_key], key=lambda t: (t[0], t[1]))
            for tid, name in entries:
                self.stdout.write(f"  {tid} | {name}")
