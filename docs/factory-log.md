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
| T07-T08 verify | delegated adversarial verifier | 1 | n/a | FAIL: 2 hangs, soft timeout, orphan loss | 0 | n/a | Sandbox itself held |
| T06b | delegated | 1 | (is rework of T06) | check.sh pass, 801 tests | 1851 | `b955cb3` | Security rework caused by verification |
| T07b | delegated | 1 | (is rework of T07/T08) | check.sh pass, 816 tests | 291 | `44d6c35` | Robustness rework caused by verification |
| T06b re-verify | delegated adversarial verifier (resumed) | 1 | n/a | PASS, 2 low residuals | 0 | n/a | Resumed the same verifier to save context |
| T09 | delegated | 1 (shared T09-T10) | 1 (OpenLP shortcut KeyError, ActionList test isolation) | check.sh pass, 913 tests | 2429 | `fa9eb62` | UI is the largest unit |
| T10 | delegated | shared | 0 | check.sh pass, 934 tests; headless OK | 582 | `aeae46b` | Service reopen after delete tested |
| T09-T10 verify | delegated adversarial verifier | 1 | n/a | FAIL: 2 editor defects + 2 low | 0 | n/a | Upload/AI isolation held |
| T06c | delegated | 1 (shared T06c-T11) | (rework of T06b) | check.sh pass, 963 tests | 134 | `78996f6` | Low residuals |
| T11 | delegated | shared | 1 (test fake) | check.sh pass, 1059 tests; headless OK | 1674 | `8c0b962` | Secrets + settings |
| T09b | delegated | 1 (shared T09b-T12) | (rework of T09) | check.sh pass, 1074 tests | 408 | `66fa62e` | Fixes from verification |
| T12 | delegated | shared | 0 | check.sh pass, 1241 tests | 2411 | `9a21107` | Largest backend unit |
| T20 | delegated | 1 (shared T20-T12b) | 0 | check.sh pass, 1270 tests, 97.28% | n/a | `8fe4dc5` | Root cause was a leaked watchdog; found only because the orchestrator re-ran the gate itself. Verifier pending |
| T12b | delegated | shared | (rework of T12) | check.sh pass, 1270 tests | n/a | `ed06c00` | Deadlines, proxy env, template depth. Verifier pending |
| T13 | delegated | 1 (shared T13-T14) | 0 | check.sh pass, 1294 tests, 97.28%; headless OK | 569 | `2190cc5` | Editor AI mode; exceeded the 400 heuristic because tests (258) and docs are included |
| T14 | delegated | shared | n/a | n/a | 0 | n/a | Stopped before coding: storage/reference design and image provider decisions are open (see feature doc) |
| T20/T12b verify | delegated adversarial verifier | 1 | n/a | FAIL: 1 medium (trickled Content-Length body and headers bypass the budget), 4 low | 0 | n/a | Chunked trickle, depth, delimiters and store races held; findings in `odd/findings/t12c-findings.md` |
| T12c | delegated | 1 | 0 | check.sh pass, 1302 tests, 97.18% | 435+/43- | `53b51d1` | RED: both trickle tests hit the 12 s test timeout on the old code. Watcher thread + tracked sockets; reworked after verification |
| T13b | delegated | 1 | 0 | check.sh pass, 1309 tests, 97.18% | 152+/14- | `c59044b` | Rework of T13 after verification; also aborts the render job on an interrupted loop (T12c finding 7). Verifier pending |
