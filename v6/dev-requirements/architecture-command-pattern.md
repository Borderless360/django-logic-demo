# Architecture: Command pattern

Side-effects, failure side-effects, callbacks, failure callbacks, conditions and
permissions are each modelled as a **Command** object wrapping a list of plain callables.

- A `Transition` owns these command objects, plus `action_name`, `sources`, `target`,
  `in_progress_state`, `failed_state`.
- The side-effects command is the orchestrator of the lifecycle: its `execute` runs the
  callables and then dispatches to the transition's success path on success or its
  failure path on exception. The transition exposes those two paths as methods (e.g.
  `complete_transition` / `fail_transition`).
- Callables receive the model instance plus transition kwargs; failure handlers also
  receive the original `exception`.

State changes go exclusively through the `State` object — see [state-locking-mechanism].
