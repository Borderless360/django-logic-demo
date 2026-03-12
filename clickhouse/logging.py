import atexit
import traceback
import json
import logging
import threading
from collections import deque
from datetime import datetime
from uuid import UUID

from clickhouse.client import client

DEFAULT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S,%f'
LOG_COLUMN_NAMES = [
    'message', 'levelname', 'filename', 'module', 'lineno', 'exc_info',
    'created', 'msecs', 'relativeCreated', 'asctime', 'name', 'pathname',
    'funcName', 'thread', 'threadName', 'processName', 'process',
    'stack_info', 'exc_text', 'msg', 'levelno', 'args', '_timestamp'
]

# Collector settings: flush when buffer reaches this many records or every N seconds
LOG_BATCH_SIZE = 1
LOG_FLUSH_INTERVAL_SEC = 5.0


class UUIDEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUID objects."""
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


class LogCollector:
    """
    Buffers log rows and flushes them to ClickHouse in batches on a background thread.
    Reduces round-trips by batching inserts instead of one insert per log record.
    """
    _instances: dict = {}
    _lock = threading.Lock()

    def __init__(self, table_name: str, batch_size: int = LOG_BATCH_SIZE, flush_interval: float = LOG_FLUSH_INTERVAL_SEC):
        self.table_name = table_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer = deque()
        self._buffer_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @classmethod
    def _flush_all(cls) -> None:
        with cls._lock:
            instances = list(cls._instances.values())
        for inst in instances:
            inst.flush()

    @classmethod
    def get_instance(cls, table_name: str = 'logs', **kwargs) -> 'LogCollector':
        with cls._lock:
            if table_name not in cls._instances:
                cls._instances[table_name] = cls(table_name=table_name, **kwargs)
                if len(cls._instances) == 1:
                    atexit.register(cls._flush_all)
            return cls._instances[table_name]

    def enqueue(self, row_data: list) -> None:
        with self._buffer_lock:
            self._buffer.append(row_data)
            if len(self._buffer) >= self.batch_size:
                rows = list(self._buffer)
                self._buffer.clear()
            else:
                rows = []
        if rows:
            self._do_insert(rows)

    def _take_buffer(self) -> list:
        with self._buffer_lock:
            if not self._buffer:
                return []
            rows = list(self._buffer)
            self._buffer.clear()
            return rows

    def _do_insert(self, rows: list) -> None:
        # if not rows or not client.db_client:
        if not rows:
            return
        try:
            # client.make_insert(self.table_name, rows, LOG_COLUMN_NAMES)
            client.insert(self.table_name, rows, column_names=LOG_COLUMN_NAMES)
        except Exception:
            pass  # Already handled in client; avoid breaking the collector

    def _run(self) -> None:
        while not self._stop.wait(timeout=self.flush_interval):
            rows = self._take_buffer()
            if rows:
                self._do_insert(rows)

    def flush(self) -> None:
        rows = self._take_buffer()
        if rows:
            self._do_insert(rows)

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.flush()


class ClickHouseHandler(logging.Handler):
    """
    Custom logging handler that sends log records to ClickHouse.
    """
    
    def __init__(self, table_name='logs', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_name = table_name
    
    def emit(self, record):
        """
        Emit a log record to ClickHouse (via batched collector).
        """
        try:
            # Format the record into a list matching the ClickHouse table structure
            log_data = [
                self.format(record) if hasattr(record, 'getMessage') else str(record.msg),
                record.levelname,
                record.filename if hasattr(record, 'filename') else None,
                record.module if hasattr(record, 'module') else None,
                record.lineno if hasattr(record, 'lineno') else None,
                self.format_exception(record.exc_info) if record.exc_info else None,
                datetime.fromtimestamp(record.created) if hasattr(record, 'created') else None,
                record.msecs if hasattr(record, 'msecs') else None,
                record.relativeCreated if hasattr(record, 'relativeCreated') else None,
                self._format_time(record) if hasattr(record, 'created') else None,
                record.name if hasattr(record, 'name') else None,
                record.pathname if hasattr(record, 'pathname') else None,
                record.funcName if hasattr(record, 'funcName') else None,
                record.thread if hasattr(record, 'thread') else None,
                record.threadName if hasattr(record, 'threadName') else None,
                record.processName if hasattr(record, 'processName') else None,
                record.process if hasattr(record, 'process') else None,
                record.stack_info if hasattr(record, 'stack_info') else None,
                record.exc_text if hasattr(record, 'exc_text') else None,
                str(record.msg) if hasattr(record, 'msg') else None,
                record.levelno if hasattr(record, 'levelno') else None,
                self._serialize_log_payload(record),
                datetime.fromtimestamp(record.created) if hasattr(record, 'created') else None,
            ]
            LogCollector.get_instance(table_name=self.table_name).enqueue(log_data)
        except Exception:
            # Don't let logging errors break the application
            # Use the base class's handleError method
            self.handleError(record)
    
    def _format_time(self, record):
        """
        Format the time for the record.
        """
        if self.formatter:
            return self.formatter.formatTime(record, self.formatter.datefmt)
        return datetime.fromtimestamp(record.created).strftime(DEFAULT_TIME_FORMAT)[:-3]

    def _serialize_log_payload(self, record):
        """
        Serialize args and custom `extra` record attributes.
        """
        payload = {}

        if hasattr(record, 'args') and record.args:
            payload['args'] = record.args

        extra = self._extract_extra(record)
        if extra:
            payload['extra'] = extra

        if not payload:
            return None

        return json.dumps(payload, cls=UUIDEncoder)

    def _extract_extra(self, record):
        """
        Extract custom fields passed via `logger.*(..., extra={...})`.
        """
        default_record_fields = set(logging.makeLogRecord({}).__dict__.keys())
        default_record_fields.update({'message', 'asctime'})
        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in default_record_fields
        }
    
    def format_exception(self, exc_info):
        """
        Format exception info into a string.
        """
        if exc_info:
            return ''.join(traceback.format_exception(*exc_info))
        return None
