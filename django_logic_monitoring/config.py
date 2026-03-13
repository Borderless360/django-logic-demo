from datetime import datetime

from django.conf import settings

DLM_CLICKHOUSE_CLIENT_PATH = getattr(settings, "DLM_CLICKHOUSE_CLIENT_PATH", "clickhouse.client.client")
DLM_DEFAULT_TIME_LIMIT = getattr(settings, "DLM_DEFAULT_TIME_LIMIT", 300)
DLM_MONITORING_DELAY = getattr(settings, "DLM_MONITORING_DELAY", 10)
DLM_MIN_EXECUTIONS = getattr(settings, "DLM_MIN_EXECUTIONS", 5)
DLM_MAX_EXECUTIONS = getattr(settings, "DLM_MAX_EXECUTIONS", 100)
DLM_LOG_PAGE_SIZE = getattr(settings, "DLM_LOG_PAGE_SIZE", 10_000)
DLM_MAX_PAGES_PER_RUN = getattr(settings, "DLM_MAX_PAGES_PER_RUN", 50)

_raw = getattr(settings, "DLM_MONITORING_SINCE", None)
DLM_MONITORING_SINCE: datetime | None = datetime.fromisoformat(_raw) if _raw else None
