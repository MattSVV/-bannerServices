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
| T01 | inline | 0 | 0 | structural readback | | | Repo bootstrap, README, license |
