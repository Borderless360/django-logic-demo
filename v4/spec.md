# v4 — Evolutionary Refactoring of django_logic

Backward-compatible refactoring of the original `django_logic` library.
Keeps the same Process/Transition/Action model but fixes the key pain points.

---

# Changes from django_logic

## TransitionContext replaces **kwargs
- Typed dataclass with explicit fields: `tr_id`, `root_id`, `parent_id`, `user`, `process_class`, `execution_mode`, `extra`
- Parent→child context propagation via `ctx.child()`
- Context-var stack via `ctx.activate()` / `TransitionContext.reset(token)`
- Serialisation helper in `utils.to_task_kwargs(ctx, state)` for Celery/MQ

## ExecutionMode enum replaces bool flags
- `SYNC` — run everything inline
- `BACKGROUND_DISPATCH` — lock + in_progress, then hand off to background worker
- `BACKGROUND_EXECUTE` — worker resumes: skip lock, run side-effects

## Single orchestrator in Transition.change_state
- lock → in_progress → side_effects → complete / fail — all visible in one method
- Commands (SideEffects, Callbacks, etc.) only run their functions, never call back into Transition

## Action is a sibling, not a child of Transition
- Action and Transition both extend BaseTransition
- Action has no lock, no in_progress, no target state

## Explicit Transition.__init__ parameters
- Named keyword arguments instead of **kwargs
- IDE autocompletion and typo detection at construction time

## No __getattr__ magic in Process
- Use `process.run(action_name, ctx=...)` explicitly

## Atomic locking by default
- `State.lock()` uses `cache.add()` (atomic set-if-not-exists)
- 1-hour TTL as safety net against abandoned locks
- No separate RedisState subclass needed

## Strict permissions
- `user is None` with permission functions → `PermissionDenied` (no silent bypass)
- No permission functions defined → pass without user

## Error handling fixed
- Side-effect failures always re-raise after `fail_transition`
- No exception swallowing at root level — caller decides
- Typed exceptions: `StateLocked`, `PermissionDenied`, `ConditionNotMet`

## No deprecated logging
- Single `logging.getLogger('django-logic.transition')` for all structured logs

---

# Data Models

## TransitionContext
Typed dataclass — replaces the old untyped **kwargs dict
**Storage:** in-memory (per-request / per-task)
**Fields**
- tr_id            UUID — unique id of this transition
- root_id          UUID — id of the top-level transition in the chain
- parent_id        UUID — id of the direct parent transition
- user             any? — the user initiating the action
- process_class    str — dotted path to the Process class
- execution_mode   ExecutionMode — SYNC | BACKGROUND_DISPATCH | BACKGROUND_EXECUTE
- extra            dict — escape hatch for custom data

---

# Business Rules

## Permissions
- When permission functions are defined, `user` must not be None
- Each function receives `(instance, user, ctx=ctx)` and returns bool
- All must return True; first failure raises PermissionDenied

## Conditions
- Each function receives `(instance, ctx=ctx)` and returns bool
- First failure raises ConditionNotMet

## Side Effects
- Executed sequentially: `fn(instance, ctx=ctx)`
- On success → `complete_transition`
- On failure → `fail_transition` then re-raise

## Callbacks
- Run after successful completion (post-unlock)
- Errors logged, not propagated

## Next Transition
- Triggered after callbacks on the same thread
- Receives a child context

---

# Runtime

## Process
Groups transitions for a model field; supports nesting

## ProcessManager
Binds Process to Django model via property descriptor
