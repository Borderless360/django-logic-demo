# State locking mechanism

State transitions are guarded by a lock held on the `State` object, accessed only through
its methods — never by mutating the field directly.

- `State.is_locked()` reports whether the object is currently locked.
- `State.lock()` acquires the lock; returns falsy if it could not be acquired.
- `State.unlock()` releases the lock.
- `State.set_state(value)` changes the persisted state value.

A transition acquires the lock before running side-effects and must release it on every
exit path. Lock acquisition failure is surfaced as `TransitionNotAllowed`.
