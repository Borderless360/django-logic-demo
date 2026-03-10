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
- steps         number - how much steps of step_type
- step_n        number - current number step
- step_type     str
- step_name     str 
- timestamp     datetime - last timestamp
- is_completed  boolean
**Constraints**
- the transition is not completed until the whole chain is completed (including child transitions)

## Stat
Execution time for  actions/transitions and their side effects
**Storage** redis
**Fields**
- id            number
- process       str
- action        str
- step_type     
- step_name     str
- last_exec     list of datetime - last DLM_MAX_EXECUTIONS execution times
- time_limit    datetime - deviation > 2σ from the mean of last_exec, default DLM_DEFAULT_TIME_LIMIT
- updated_at    datetime
**Constraints**
- process, action, step_type, step_name - unique together
- time_limit count only if last_exec has min DLM_MIN_EXECUTIONS items 

## Anomaly
Detected execution time anomaly
Anomaly is long execution based on statistics of previous runs,
deviation > 2σ from the mean, minimum DLM_MIN_EXECUTIONS records
**Storage** redis
**Fields**
- id            number 
- tr_id         -> Transition 
- current_exec  datetime
- timestamp     datetime when we detect it

## Config
**Storage** Django settings
**Fields**
- DLM_CLICKHOUSE_CLIENT_PATH
- DLM_DEFAULT_TIME_LIMIT
- DLM_MONITORING_DELAY
- DLM_MIN_EXECUTIONS
- DLM_MAX_EXECUTIONS 

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
  do: detect anomaly
  do: send notification to console about new anomaly
- *clear*
  do: remove completed transitions
  do: remove other garbage

-------------------------------------------------------------------------------
# Runtime
Logical units that compose the running service.
Defines *what* must be running, not *how* it is deployed.

## django-logic-monitoring-worker
Celery worker where running main task

-------------------------------------------------------------------------------
# Others
## Django manager commands
**dlm_get_current_transitions** return active transitions with states
**dlm_fetch_logs** run fetch_logs action
**dlm_detect_anomaly** run detect_anomaly action
