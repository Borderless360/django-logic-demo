from __future__ import annotations

from datetime import datetime

from clickhouse.client import client


class ClickHouseSource:
    def fetch_logs(self, *, since: datetime | None, limit: int = 5000) -> list[dict]:
        where_parts = ["name = 'django-logic.transition'"]
        if since is not None:
            since_str = since.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            where_parts.append(f"_timestamp > toDateTime64('{since_str}', 3)")
        where_sql = " AND ".join(where_parts)
        query = f"""
            SELECT message, _timestamp
            FROM logs
            WHERE {where_sql}
            ORDER BY _timestamp ASC
            LIMIT {int(limit)}
        """
        result = client.query(query)
        if not result.result_rows:
            return []
        names = result.column_names
        return [dict(zip(names, row)) for row in result.result_rows]

