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
| T04 | delegated | 1 (shared T04-T06) | 1 (exception hierarchy, test messages) | check.sh pass | 1006 | `08bc47c` | Exceeded the 400 heuristic: 65 scripture tests |
| T05 | delegated | shared | 1 (4 test bugs) | check.sh pass | 1178 | `66fafe4` | Templates + icons + fonts; visual parity checked |
| T06 | delegated | shared | 1 (corpus fixes, idempotence, svg) | check.sh pass, 350 tests | 969 | `cce22a7` | Malicious payload corpus |
| T02/T03 verify | delegated verifier | 1 | 0 | 6/6 PASS | 0 | n/a | Independent check for high-risk shell scripts |
| T04-T06 verify | delegated adversarial verifier | 1 | n/a | **FAIL: 5 bypasses + regex DoS** | 0 | n/a | Green tests did not mean safe; reopened as T06b |
| T07 | delegated | 1 (shared T07-T08) | 1 (white-frame race fixed with a canary) | check.sh pass | ~1086 | `4b5df9c` | Headless QtWebEngine works offscreen |
| T08 | delegated | shared | 0 | check.sh pass, 533 tests | ~1203 | `b038b4b` | Traversal-safe repo + use case |
