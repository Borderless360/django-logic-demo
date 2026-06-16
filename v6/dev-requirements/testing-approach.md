# Testing approach

Behaviour is verified with pytest against a Django test model that has a state field and
a process.

- Each user-story acceptance criterion maps to at least one test.
- Side-effects, callbacks and their failure variants are plain functions injected per
  test; to exercise a failure, inject one that raises.
- Tests assert on observable outcomes only: the final state value, whether the lock is
  released (`State.is_locked()`), and which injected callables ran (e.g. via a spy/list).
- Errors that are meant to be swallowed are asserted by confirming the call returns and
  the lock is released — not by inspecting internal state.
- Logging is not asserted on (see [logging-convention]); it is not part of the contract.
