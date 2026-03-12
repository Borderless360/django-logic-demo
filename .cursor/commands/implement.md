1. **Detect changes.** Run `git diff -- '*/spec.md' 'spec.md'` and `git diff --cached -- '*/spec.md' 'spec.md'` to collect both staged and unstaged changes across all spec files (root and per-app). If there are no changes — stop and tell the user.

2. **Read full specs.** For every changed `spec.md`, read the entire file so you have full context — not just the diff hunks.

3. **Implement.** Apply changes app-by-app. After each app:
   - Run linter checks on modified files.
   - Generate migrations if models changed.
   - Run tests (`make test`) — fix any failures before moving on.
