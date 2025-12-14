
def is_planned(lock):
    return lock.customer_received_notice


def is_lock_available(lock):
    return lock.is_available
