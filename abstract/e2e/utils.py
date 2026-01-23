import time
from django_logic.state import State
from clickhouse.client import client
from django_logic.logger import TransitionEventType


def wait_state_unlock(state: State, max_retries: int = 10, retry_delay: float = 0.5) -> bool:
    """
    Wait for a state to be unlocked.
    """
    for attempt in range(max_retries):
        if not state.is_locked():
            return True
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return False


def check_logs(transition_id: str, event_type: TransitionEventType, max_retries: int = 5, retry_delay: float = 0.1) -> bool:
    """
    Check if transition has logs with event type.
    Returns True if logs are found, False otherwise.
    
    Includes retry logic to handle potential async writes to ClickHouse.
    
    :param transition_id: The transition ID to search for
    :param event_type: The event type to check for
    :param max_retries: Maximum number of retry attempts
    :param retry_delay: Delay between retries in seconds
    :return: True if logs found, False otherwise
    """
    # Convert UUID to string if needed
    transition_id_str = str(transition_id)
    pattern = f"{transition_id_str} {event_type.value}%".replace("'", "''")
    query = f"""
        SELECT COUNT(*) as count
        FROM logs
        WHERE message LIKE '{pattern}'
    """
    
    for attempt in range(max_retries):
        try:
            result = client.query(query)
            # Get the count from the result
            if result.result_rows:
                count = result.result_rows[0][0]
                if count > 0:
                    return True
            
            # If not found and not last attempt, wait and retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as e:
            # If error occurs and not last attempt, wait and retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise
    
    return False


def get_logs_by_tr_id(tr_id, max_retries: int = 5, retry_delay: float = 0.1, as_dict: bool = False):
    """
    Get all logs for a given transition ID from ClickHouse.
    
    Includes retry logic to handle potential async writes to ClickHouse.
    
    :param tr_id: The transition ID to search for (can be UUID or string)
    :param max_retries: Maximum number of retry attempts
    :param retry_delay: Delay between retries in seconds
    :param as_dict: If True, return list of dictionaries with column names as keys. 
                    If False, return list of tuples (default).
    :return: List of log records (tuples or dictionaries depending on as_dict parameter)
    """
    # Convert UUID to string if needed
    tr_id_str = str(tr_id)
    # Escape single quotes in the tr_id for SQL safety
    tr_id_escaped = tr_id_str.replace("'", "''")
    query = f"""
        SELECT *
        FROM logs
        WHERE message LIKE '{tr_id_escaped} %'
        ORDER BY _timestamp ASC, created ASC, message ASC
    """
    
    for attempt in range(max_retries):
        try:
            result = client.query(query)
            # Return all result rows
            if result.result_rows:
                if as_dict:
                    # Get column names from result
                    column_names = result.column_names
                    # Convert each row tuple to a dictionary
                    return [dict(zip(column_names, row)) for row in result.result_rows]
                else:
                    return result.result_rows
            
            # If not found and not last attempt, wait and retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as e:
            # If error occurs and not last attempt, wait and retry
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise
    
    return []


def verify_celery_worker_running(celery_app, max_retries: int = 5, retry_delay: float = 0.1) -> bool:
    """
    Verify that the Celery worker is actually running by executing a test task.
    
    :param celery_app: The Celery app instance
    :param max_retries: Maximum number of retry attempts
    :param retry_delay: Delay between retries in seconds
    :return: True if worker is running and can execute tasks, False otherwise
    """
    try:
        # Use Celery's control API to ping workers directly
        # This doesn't require a result backend
        inspect = celery_app.control.inspect()
        for attempt in range(max_retries):
            try:
                # Ping the workers
                response = inspect.ping()
                if response:
                    # Response is a dict mapping worker names to their responses
                    # If we get any response, workers are running
                    return True
            except Exception:
                # If ping fails, wait and retry
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return False
        
        return False
    except Exception as e:
        # If we can't even inspect workers, they're not running
        return False
