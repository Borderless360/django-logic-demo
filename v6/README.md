# django-logic

A declarative state machine for Django models: define states, transitions, side-effects
and callbacks on a process, and trigger transitions by action name.

> Generated from `user-story/`. Do not hand-edit — change the stories and regenerate
> (see [AGENTS.md](AGENTS.md)).

## Install

```bash
pip install django-logic
```

## Recovering from a failed side-effect

Declare a transition with side-effects, a `failed_state`, and failure callbacks. If a
side-effect raises, the object is moved to the failed state, your failure callbacks run,
and the lock is released — the object never gets stuck mid-transition.

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

Side-effects after the failing one do not run, and the normal (success) callbacks do not
run.

## Failure handlers can't break a transition

If your own failure handlers (failure side-effects or failure callbacks) raise, the error
is logged and swallowed — never propagated. A bug in a failure handler can't leave the
object locked or mask the original failure.

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
obj.state           # -> "approval_failed"; object is unlocked
```
