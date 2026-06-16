# Logging convention

Transition lifecycle events are emitted through a single structured logger
(`transition_logger`) using a fixed set of event types (start, lock, set-state,
side-effect, callback, failure-side-effect, unlock, fail, ...).

- Each log line carries the transition id and the relevant identifiers.
- Errors caught on the failure path (including errors swallowed inside failure handlers)
  are logged at error level with the exception attached.
- Logging is side-effect free with respect to control flow: a logging failure must never
  alter transition behaviour.
