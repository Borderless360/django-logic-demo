# Django Logic v3
State-machine library for Django models where each business transaction
is a single class with one entry point: `do()`.

---
# Core Idea

**One Transaction — One Class.**

Every business operation — whether it changes state or not — is represented
by exactly one class (Action or Transition). The class owns the full lifecycle
of the operation: validation, execution, and chaining to the next step.

This differs from the original django-logic where behaviour was spread
across Process-level callbacks, side-effects, and transition definitions.
In v3 everything lives inside the class that performs the work:
- `is_available` — guards and preconditions
- `do()` — the operation itself
- `next` — optional follow-up action (chain)

A Process is only a container that groups available actions for a model field.

---
# Public API

## Action
Base class for a business operation that does not change model state.

**Params**
- name        str           — human-readable action name (class-level)
- process     Process?      — back-reference to owning process, set at runtime
- next        Action?       — optional chained action to run after this one

**Methods**
- is_available -> bool      — whether the action can run (default: True)
- do() -> UUID              — execute the operation, return a unique action id

**Constraints**
- Subclass and override `do()` to add real logic
- `is_available` is checked before `do()` by the Process

## Transition
Action subclass that additionally moves the model between states.

**Params** (extends Action)
- sources             list[str]   — allowed source states
- target              str         — state after success
- in_progress_state   str         — intermediate state during execution
- failed_state        str         — state on failure

**Methods**
- is_available -> bool  — True only when current state is in `sources`
- do() -> UUID          — execute the transition

**Constraints**
- Current model state must be in `sources` before `do()` is called
- On success the model moves to `target`
- On failure the model moves to `failed_state`

## Process
Groups transitions and actions for a single model state field.

**Params**
- transitions   list[Action | Transition]   — available operations

**Constraints**
- A model may have multiple Processes (one per state field)
- Process resolves which transitions are available based on current state

---
# Constraints

- One Action = one transaction; all logic lives inside the class
- State is stored on the Django model field, not inside the library
- Chaining: `next` allows sequential composition without external orchestration
- No magic `__getattr__` — actions are explicit class instances
- The library does not manage locking or background execution (v4 adds those)

---
# Usage

```python


obj.process.action()


class BasicProcess(BaseProcess):
    transitions = [
        Transition(ActionA,
            sources=[STATES.A], target=STATES.B,
            side_effects=[error_for_superuser],
            failure_side_effects=[save_error],
        ),
        Transition(
            action_name='fail_callback', sources=[STATES.A], target=STATES.B,
            callbacks=[error_for_superuser, short_action],
        ),
    ]


действия без аргументов?
def some_action(obj)


class MakeReport(Action):
    name = 'MakeReport'

    def do(self):
        action_id = super().do()
        # ... generate the report ...
        return action_id

class SendReport(Action):
    name = 'SendReport'

class ReportingProcess(Process):
    transitions = [
        MakeReport(next=SendReport()),
        SendReport(),
    ]
```
