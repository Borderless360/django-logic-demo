# Failure handlers cannot break a transition

As a developer using django-logic, my failure handlers (failure side-effects or failure
callbacks) sometimes have bugs and raise. I want those errors logged and swallowed, not
propagated — so a bug in a failure handler can never leave the object locked or mask the
original failure.

## How I want to use it

```python
Transition(
    action_name="approve",
    sources=["draft"],
    target="approved",
    failed_state="approval_failed",
    side_effects=[charge_card],          # raises -> failure path starts
    failure_side_effects=[rollback],     # rollback() itself raises
    failure_callbacks=[alert_support],   # alert_support() itself raises
)

process.approve()   # returns normally; nothing propagates out
obj.state           # -> "approval_failed"
# object is unlocked; both handler errors are in the log
```

## Rough algorithm I expect

```
while running the failure path:
  if a failure side-effect raises: log it, keep going (still release the lock)
  if a failure callback raises:    log it, keep going
the original error is passed to the handlers but is never re-raised
```

## Acceptance criteria

- Given a failing side-effect and a failure side-effect that itself raises, the state
  lock is still released.
- Given a failing side-effect and a failure callback that itself raises, the transition
  call returns without propagating that exception.
- An error raised inside a failure handler is written to the log.
- The object still reaches the failed state regardless of errors in failure handlers.
