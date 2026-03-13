# Django Logic Monitoring
Django app of monitoring `django-logic` logs for detecting anomalies
and performing actions in response to detected anomalies

-------------------------------------------------------------------------------
# Data Models
Models are ordered by importance: core entities first, then their dependencies
type? - not required
-> one to many  
-- one to one

## Log 
Django Logic logs
**Source:** Django Logic 
- logs table from clickhouse
**Constraints**
- read only 

## LastLogTimestamp
A global value of timestamp of last reading log
**Storage** redis
**Fields**
- timestamp     datetime

## Transition
State of django logic transition 
**Storage** redis
**Fields**
- id            UUID
- parent_id     -> Transition 
- root_id       -> Transition
- process       str - name of process
- model_name    str
- object_id     str
- field_name    str - field with state
- steps         number - how many steps of step_type
- step_n        number - current step number
- step_type     str
- step_name     str 
- timestamp     datetime - last timestamp
- is_completed  boolean
**Constraints**
- the transition is not completed until the whole chain is completed (including child transitions)

## Stat
Execution time for actions/transitions and their side effects (no callbacks)
**Storage** redis
**Fields**
- id            number
- process       str
- action        str
- step_type     str
- step_name     str
- last_exec     list of datetime - last DLM_MAX_EXECUTIONS execution times
- time_limit    datetime - deviation > 2σ from the mean of last_exec, default DLM_DEFAULT_TIME_LIMIT
- updated_at    datetime
**Constraints**
- process, action, step_type, step_name - unique together
- time_limit is computed only when last_exec has at least DLM_MIN_EXECUTIONS items

## AnomalyType
**Storage** python enum
- id            number 
- name          str

## Anomaly
The fact of catch an anomaly into the transition.
**Storage** redis
**Fields**
- id            number 
- tr_id         -> Transition 
- process       str
- action        str
- step_type     str
- step_name     str
- type          -> AnomalyType
- timestamp     datetime when we detect it
**Constraints**
- tr_id, type - unique together

## Config
**Storage** Django settings
**Fields**
- DLM_CLICKHOUSE_CLIENT_PATH  str - dotted import path to ClickHouse client (default "clickhouse.client.client")
- DLM_DEFAULT_TIME_LIMIT      number - fallback time limit in seconds when too few executions for statistical threshold (default 300)
- DLM_MONITORING_DELAY        number - interval in seconds between monitoring runs (default 10)
- DLM_MIN_EXECUTIONS          number - minimum recorded executions required to compute statistical time_limit (default 5)
- DLM_MAX_EXECUTIONS          number - max execution times kept per Stat record (default 50)
- DLM_MAX_PAGES_PER_RUN       number - max log pages fetched per single monitoring run (default 50)
- DLM_MONITORING_SINCE        datetime? - ignore logs before this timestamp

-------------------------------------------------------------------------------
# Business Rules

## Jobs
Scheduled or event-driven tasks that run without user interaction.
Defines *what* should happen and *when* (business rule).
- monitoring | celery: every DLM_MONITORING_DELAY seconds | run fetch_logs and detect_anomaly actions of main process

## Main Process
**Actions**
- *fetch_logs*
  do: read logs
  do: update transitions
  do: remove completed transitions (with or without errors)
  do: update stats
- *detect_anomaly*
  do: detect `logn execution` anomaly
  do: send notification to console about new anomaly
- *clear*
  do: remove completed transitions
  do: remove other garbage

## Anomaly
**Long execution**
Anomaly long execution of side effects based on statistics of previous runs,
deviation > 2σ from the mean, minimum DLM_MIN_EXECUTIONS records

-------------------------------------------------------------------------------
# Runtime
Logical units that compose the running service.
Defines *what* must be running, not *how* it is deployed.

## django-logic-monitoring-worker
Celery worker that runs the monitoring task

-------------------------------------------------------------------------------
# Others
## Django manager commands
**dlm_get_current_transitions** return active transitions with states
**dlm_fetch_logs** run fetch_logs action
**dlm_detect_anomaly** run detect_anomaly action
**dlm_get_stats** show collected execution-time statistics
**dlm_get_anomalies** show detected execution-time anomalies
**dlm_clear_stats** clear all collected execution-time statistics
