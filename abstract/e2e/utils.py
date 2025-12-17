import time
from typing import List, Dict, Set
from clickhouse.client import client
from django_logic.logger import TransitionEventType


def wait_for_transition(instance, expected_state: str, max_retries: int = 10, retry_delay: float = 0.2) -> bool:
    """
    Wait for a transition to complete by checking if the instance's state matches the expected state.
    This is useful when transitions are executed as Celery tasks and we need to wait for them to complete.
    
    :param instance: The model instance to check
    :param expected_state: The expected state value
    :param max_retries: Maximum number of retry attempts
    :param retry_delay: Delay between retries in seconds
    :return: True if state matches expected state, False otherwise
    """
    for attempt in range(max_retries):
        instance.refresh_from_db()
        # Get the status field (assuming it's called 'status')
        current_state = getattr(instance, 'status', None)
        if current_state == expected_state:
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
