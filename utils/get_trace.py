from django.apps import apps
from clickhouse.client import client


def get_trace_clickhouse(model_name, instance_id ):
    """Get grouped ClickHouse logs for all instance start transitions."""
    model = apps.get_model(model_name)
    instance = model.objects.get(pk=instance_id)

    instance_key = f"-{model_name}-%-{instance.pk}"
    instance_key_escaped = instance_key.replace("'", "''")

    start_query = f"""
        SELECT *
        FROM logs
        WHERE message LIKE '% Start % {instance_key_escaped} %'
        ORDER BY _timestamp ASC, created ASC, message ASC
    """
    start_result = client.query(start_query)
    if not start_result.result_rows:
        return {}

    start_column_names = start_result.column_names
    start_rows = [dict(zip(start_column_names, row)) for row in start_result.result_rows]

    # First token of each message is the transition id.
    tr_ids = []
    for row in start_rows:
        message = row.get('message', '')
        tr_id = message.split(' ', 1)[0].strip()
        if tr_id and tr_id not in tr_ids:
            tr_ids.append(tr_id)

    logs_by_tr_id = {}
    for tr_id in tr_ids:
        tr_id_escaped = tr_id.replace("'", "''")
        logs_query = f"""
            SELECT *
            FROM logs
            WHERE message LIKE '{tr_id_escaped} %'
            ORDER BY _timestamp ASC, created ASC, message ASC
        """
        logs_result = client.query(logs_query)
        log_column_names = logs_result.column_names
        logs_by_tr_id[tr_id] = [
            dict(zip(log_column_names, row)) for row in logs_result.result_rows
        ]

    return {
        'instance_key': instance_key,
        'start_transitions': start_rows,
        'logs_by_tr_id': logs_by_tr_id,
    }