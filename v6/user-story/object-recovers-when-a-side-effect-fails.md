# Object recovers when a side-effect fails

As a developer using django-logic, I declare a transition with a list of side-effects, a
`failed_state`, and failure callbacks. When I trigger the transition and one of the
side-effects raises, I want the object to be recovered into the failed state, my failure
callbacks to run, and the lock released — so the object never gets stuck mid-transition.

## How I want to use it

```python
class MyProcess(Process):
    transitions = [
        Transition(
            action_name="approve",
            sources=["draft"],
            in_progress_state="approving",
            target="approved",
            failed_state="approval_failed",
            side_effects=[charge_card, notify_warehouse],   # charge_card raises
            failure_callbacks=[alert_support],
        ),
    ]

process.approve()   # charge_card raises inside the transition
obj.state           # -> "approval_failed"  (not "approving", not "approved")
```

## Rough algorithm I expect

```
run side-effects one by one in order
  on the first one that raises (call it `error`):
    stop — do not run the remaining side-effects
    if failed_state is set: set state = failed_state
    run failure side-effects (passing error)
    release the lock
    run failure callbacks (passing error)
  if all succeed:
    set state = target, release lock, run normal callbacks
```

## Acceptance criteria

- Given a transition with a `failed_state` and a side-effect that raises, when the
  transition runs, the object's state ends as `failed_state`.
- The state lock is released after the failure.
- The configured failure callbacks run and receive the raised exception.
- Side-effects declared after the failing one do NOT run.
- The transition's normal (success) callbacks do NOT run.
- The object's state is never left as the in-progress state once the transition returns.
