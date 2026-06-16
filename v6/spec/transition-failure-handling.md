# transition-failure-handling

Behaviour of a transition when a side-effect fails: how the object is recovered into the
failed state, how the lock is released, and how failure handlers are isolated.

Derived from user-stories `object-recovers-when-a-side-effect-fails` and
`failure-handlers-cannot-break-a-transition`, honouring dev-requirements
`architecture-command-pattern`, `state-locking-mechanism`, `logging-convention`,
`testing-approach`.

## Scope

The side-effect execution stage of a transition that has already acquired the state lock
and (optionally) set its in-progress state. Implemented in the side-effects Command's
`execute`, dispatching to the transition's success/failure path methods
(`architecture-command-pattern`).

## Behaviour

### Side-effect execution

- Side-effects run sequentially, in declaration order, each invoked with the model
  instance and transition kwargs.
- On the first side-effect that raises, the chain stops immediately; no later side-effect
  runs. The exception `error` is logged (`logging-convention`) and the transition enters
  the **failure path** with it.
- If all side-effects succeed, the transition enters its success path: set `target`,
  release the lock, run normal callbacks. Failure handlers do not run.

### Failure path

Given the captured `error`, in order:

1. **Set failed state.** If `failed_state` is configured, `State.set_state(failed_state)`.
   Otherwise leave the state unchanged (see Open question).
2. **Run failure side-effects**, passing `exception=error`. Any exception raised here is
   caught, logged, and discarded; it must not abort the remaining steps.
3. **Release the state lock** via `State.unlock()`. Always executed, regardless of step 2.
4. **Run failure callbacks**, passing `exception=error`. Any exception raised here is
   caught, logged, and discarded.

The original `error` is never re-raised by these steps.

## Guarantees

- The lock is released on every path, success or failure (`state-locking-mechanism`).
- A buggy failure handler can neither leave the object locked nor mask the failure path:
  steps 1–4 complete regardless of exceptions thrown in steps 2 and 4.
- Success callbacks never run on the failure path; failure callbacks never run on the
  success path.

## Tests to emit (per `testing-approach`, from acceptance criteria)

1. failing side-effect + `failed_state` ⇒ final state == `failed_state`.
2. failing side-effect ⇒ lock released (`State.is_locked()` is false).
3. failing side-effect ⇒ failure callbacks ran and received the exception.
4. failing side-effect ⇒ side-effects after the failing one did not run.
5. failing side-effect ⇒ success callbacks did not run.
6. failure side-effect raises ⇒ lock still released.
7. failure callback raises ⇒ transition call returns without propagating.
8. error inside a failure handler ⇒ object still reaches failed state, call returns.

## Open question (for human review)

US `object-recovers-when-a-side-effect-fails` asserts "state is never left as the
in-progress state once the transition returns", but step 1 leaves the state unchanged
when no `failed_state` is configured. These conflict when `failed_state` is absent.
Resolve by either (a) making `failed_state` mandatory, or (b) falling back to the source
state on failure. **Needs a decision before src generation.**
