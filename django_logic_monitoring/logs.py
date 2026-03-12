from datetime import datetime

from django.utils.module_loading import import_string

from django_logic_monitoring.config import DLM_CLICKHOUSE_CLIENT_PATH


def _get_client():
    return import_string(DLM_CLICKHOUSE_CLIENT_PATH)


def fetch_logs_since(since: datetime | None = None) -> list[dict]:
    """Fetch transition logs from ClickHouse since the given timestamp."""
    ch = _get_client()

    if since:
        ts_str = since.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        query = (
            "SELECT message, _timestamp FROM logs "
            "WHERE name = 'django-logic.transition' "
            f"AND _timestamp > toDateTime64('{ts_str}', 3) "
            "ORDER BY _timestamp"
        )
    else:
        query = (
            "SELECT message, _timestamp FROM logs "
            "WHERE name = 'django-logic.transition' "
            "ORDER BY _timestamp"
        )

    result = ch.query(query)
    return [
        {"message": row[0], "timestamp": row[1]}
        for row in result.result_rows
    ]
