# Django Logic
State-machine and workflow engine for Django models.
Manages state transitions with locking, permissions, conditions,
side effects, and background execution via Celery.

-------------------------------------------------------------------------------
# Data Models
Models are ordered by importance: core entities first, then their dependencies
type? - not required
-> one to many
-- one to one

## Transition
State change from one of `sources` to `target`, guarded by conditions
and permissions, executing a pipeline of side effects and callbacks
**Fields**
- action_name           str - callable name used by the process
- sources               list of str - allowed source states
- target                str - destination state
- in_progress_state     str? - intermediate state set before side effects
- failed_state          str? - state set on side-effect failure
- side_effects          list of callable
- callbacks             list of callable - run after success
- failure_callbacks     list of callable - run after failure
- failure_side_effects  list of callable - run after failure, before unlock
- permissions           list of callable(instance, user) -> bool
- conditions            list of callable(instance) -> bool
- next_transition       str? - action name to chain after completion
- queue_name            str - Celery queue, default DJANGO_LOGIC_DEFAULT_QUEUE

## BackgroundTransition
Transition that is pushed to Celery by default

## Action
Transition that does not change state on success (empty target).
No locking. failed_state still applies on failure.

## Process
Named group of transitions and nested sub-processes bound to a model state field
**Fields**
- process_name      str - identifier, default "process"
- transitions       list of Transition
- nested_processes  list of Process classes
- conditions        list of callable - apply to all transitions
- permissions       list of callable - apply to all transitions
- state_class       class - State or RedisState, default State
- queryset_name     str - model manager name, default "objects"

## State
Wrapper around a model instance's state field; provides read, write, and cache-based locking
**Storage** Django cache (Redis)
**Fields**
- instance       any Django model instance
- field_name     str - model field that holds the state value
- process_name   str?
- queryset_name  str - default "objects"
**Constraints**
- instance_key = "{app_label}-{model_name}-{field_name}-{pk}"
- lock key = BLAKE2b hash of instance_key
- lock via Django cache with ~permanent TTL; explicit unlock required

## RedisState
State with optimistic locking (cache set nx=True); only first caller acquires the lock

## Config
**Storage** Django settings
**Fields**
- DJANGO_LOGIC_DEFAULT_QUEUE      str - Celery queue for background transitions (default "celery")
- DJANGO_LOGIC_DISABLE_LOGGING    bool - disable deprecated logger (default False)
- DJANGO_LOGIC_CUSTOM_LOGGER      str? - dotted import path to custom logger class

-------------------------------------------------------------------------------
# Business Rules

## Transition Lifecycle
**Transition execution**
1. Lock state (skip if background phase 2)
2. Set in_progress_state if defined
3. If background mode and not phase 2 -> push to Celery queue (phase 1 ends)
4. Run side effects sequentially
5. On success -> set target, unlock, run callbacks, run next_transition if defined
6. On failure -> set failed_state if defined, run failure_side_effects, unlock, run failure_callbacks

**Action execution**
1. Run side effects sequentially (no locking, no in_progress_state)
2. On success -> run callbacks
3. On failure -> set failed_state if defined, run failure_side_effects, unlock, run failure_callbacks

## Process Dispatch
- Resolves action_name to exactly one matching transition
  (current state in sources, conditions met, permissions met)
- Multiple matches -> TransitionNotAllowed
- No match -> TransitionNotAllowed
- Dynamic method access: `process.action_name()` dispatches the transition

## Permissions & Conditions
- Conditions: all must return True (AND)
- Permissions: all must return True for the given user; skipped when user is None
- Process-level conditions/permissions gate all nested transitions

## Locking
- State is locked before side effects and unlocked after completion or failure
- Locked state blocks new transitions (raises TransitionNotAllowed)
- RedisState guarantees only one caller acquires the lock (race-safe via nx)

## Nested Transitions
- Process supports nested sub-processes; available transitions include all nested
- Transition context (root_id, parent_id, tr_id) propagates via ContextVar
- Root transition catches exceptions silently and returns tr_id
- Nested transitions propagate exceptions to their parent

## Background Execution (two-phase)
- Phase 1: lock state, set in_progress_state, push Celery task
- Phase 2: worker restores instance, runs side effects with lock already held
- Child transitions invoked during phase 2 side_effects or failure_side_effects
  run inline (already inside the worker)

## defer
- `defer(func)` / `defer(func, queue_name)` returns a **callable**; invoking that
  callable submits `func` to run in its **own** Celery task (on `queue_name` or the
  default queue when omitted), instead of running `func` in the current thread

## Model Binding
- ProcessManager.bind_model_process: adds a property on the model that returns
  a Process instance for the given state field

## Logging
- `django-logic` logger: general activity
- `django-logic.transition` logger: structured transition events
  (Start, Complete, Fail, SideEffect, Callback, FailureSideEffect,
  Set State, Lock, Unlock, Next Transition, Background Mode)

-------------------------------------------------------------------------------
# Runtime

## django-logic-worker
Celery worker that executes background transitions (django_logic_background task)

## Dependencies
- Django cache backend (Redis) for state locking
- Celery broker + worker for background transitions
- django.contrib.auth User model when user_id is passed in background tasks
