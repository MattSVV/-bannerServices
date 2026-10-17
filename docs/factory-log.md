# Factory log

One row per backlog task: how the factory executed it and what it cost. It is updated after every work-unit commit.

## Metrics

| Metric | Meaning |
|--------|---------|
| Route | `inline` (orchestrator did it) or `delegated` (writer agent did it) |
| Delegations | Agent runs used for the task (writers, reviewers, verifiers) |
| Rework | Extra rounds caused by failed checks or wrong output |
| Gate | Result of `scripts/check.sh` (or the focused check before it existed) |
| Lines | Authored lines changed (additions + deletions) |

## Run 1 — overnight autonomous run (2026-10-16)

| Task | Route | Delegations | Rework | Gate | Lines | Commit | Notes |
|------|-------|-------------|--------|------|-------|--------|-------|
| T01 | inline | 0 | 0 | structural readback | ~254 (excl. LICENSE) | `da600a0` | Repo bootstrap, README, license |
| T02 | delegated | 1 (shared with T03) | 0 | check.sh pass (after T03) | 155 | `aee17fc` | Gate committed before any test existed |
| T03 | delegated | 1 (shared with T02) | 1 (missing default setting found by runtime harness) | check.sh pass; headless harness OK | 385 | `33fc722` | Runtime harness caught a bug unit tests missed |
