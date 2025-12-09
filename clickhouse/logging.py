import logging
import json
from datetime import datetime
from clickhouse.client import client


class ClickHouseHandler(logging.Handler):
    """
    Custom logging handler that sends log records to ClickHouse.
    """
    
    def __init__(self, table_name='logs', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.table_name = table_name
    
    def emit(self, record):
        """
        Emit a log record to ClickHouse.
        """
        try:
            # Define column names in the order they appear in the table (excluding _timestamp which has DEFAULT)
            column_names = [
                'message', 'levelname', 'filename', 'module', 'lineno', 'exc_info',
                'created', 'msecs', 'relativeCreated', 'asctime', 'name', 'pathname',
                'funcName', 'thread', 'threadName', 'processName', 'process',
                'stack_info', 'exc_text', 'msg', 'levelno', 'args'
            ]
            
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
                self.format_exception(record.exc_info) if record.exc_info else None,
                str(record.msg) if hasattr(record, 'msg') else None,
                record.levelno if hasattr(record, 'levelno') else None,
                json.dumps(record.args) if hasattr(record, 'args') and record.args else None,
            ]
            
            # Insert into ClickHouse with explicit column names
            client.insert(self.table_name, [log_data], column_names=column_names)
            
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
        else:
            return datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
    
    def format_exception(self, exc_info):
        """
        Format exception info into a string.
        """
        if exc_info:
            import traceback
            return ''.join(traceback.format_exception(*exc_info))
        return None
