# Django Logic Monitoring
Monitoring `django-logic` logs: detects anomalies and performs actions
in response to detected anomalies

## Data Flow
Source → ActiveTransition → Stats → Anomaly → ActionConfig → Action

## Entities

**Source** — source of `django-logic` logs
- SRC-1: sources may vary
- SRC-2: default source is ClickHouse

**ActiveTransition** — state of a running transition
- AT-1: A transition is active until the whole chain is completed (including child transitions)
- AT-2: Completed transitions (with or without errors) are removed from the list
- AT-3: States are stored in memory, but in case of failure they must be restored from Redis.

**Stats** — execution time statistics
- S-1: collected for actions/transitions and their side effects
- S-2: stored in Redis
- S-3: storage TTL is 30 days

**Anomaly** — anomaly detection algorithm
- Anom-1: long execution based on statistics of previous runs,
    deviation > 2σ from the mean, minimum 5 records

**Action** — executed action
- Action-1: send email
- Action-2: call API/webhook

**ActionConfig** — action configuration for specific anomalies
- AC-1: configured in Django settings
- AC-2: multiple actions can be configured for one anomaly
- AC-3: an action is executed only once when an anomaly is detected

**Monitoring** — process that performs monitoring
- Mon-1: singleton listener process in a separately launched task
- Mon-2: log listening in near-real-time (up to 5 sec delay)
- Mon-3: auto-recovery after failure (task restart)

## Constraints
- Python 3.12+, Django 4.2+, Celery
- Must not block the main Django application
- Everything must be covered by tests using pytest.

## User action
- UA-1: can view active transitions at any time
