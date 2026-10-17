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
| T11-T12 verify | delegated adversarial verifier | 1 | n/a | FAIL: 2 medium (no total deadline on provider replies, uncaught `RecursionError`), 3 low | 0 | n/a | Findings in `odd/findings/t12b-findings.md`; opened T12b (and T20, found separately by the orchestrator) |
| T13 verify | delegated adversarial verifier | 1 | n/a | FAIL: 1 low-medium (unexpected factory errors escaped the slot), 3 low, 1 info | 0 | n/a | Findings in `odd/findings/t13b-findings.md`; opened T13b |
| T20 | delegated | 1 (shared T20-T12b) | 0 | check.sh pass, 1270 tests, 97.28% | n/a | `8fe4dc5` | Root cause was a leaked watchdog; found only because the orchestrator re-ran the gate itself. Verified by the T20/T12b verify row |
| T12b | delegated | shared | (rework of T12) | check.sh pass, 1270 tests | n/a | `ed06c00` | Deadlines, proxy env, template depth. Verified by the T20/T12b verify row (1 medium left) |
| T13 | delegated | 1 (shared T13-T14) | 0 | check.sh pass, 1294 tests, 97.28%; headless OK | 569 | `2190cc5` | Editor AI mode; exceeded the 400 heuristic because tests (258) and docs are included |
| T14 | delegated | shared | n/a | n/a | 0 | n/a | Stopped before coding: storage/reference design and image provider decisions are open (see feature doc) |
| T20/T12b verify | delegated adversarial verifier | 1 | n/a | FAIL: 1 medium (trickled Content-Length body and headers bypass the budget), 4 low | 0 | n/a | Chunked trickle, depth, delimiters and store races held; findings in `odd/findings/t12c-findings.md` |
| T12c | delegated | 1 | 0 | check.sh pass, 1302 tests, 97.18% | 435+/43- | `53b51d1` | RED: both trickle tests hit the 12 s test timeout on the old code. Watcher thread + tracked sockets; reworked after verification |
| T13b | delegated | 1 | 0 | check.sh pass, 1309 tests, 97.18% | 152+/14- | `c59044b` | Rework of T13 after verification; also aborts the render job on an interrupted loop (T12c finding 7). Verified by the T15 review |
| T16 | delegated | 1 | 0 | check.sh pass, 1321 tests, 97.43%; headless + E2E OK | ~430+/1- | `8c2b261`, `2e94ea8`, `d25245d` | CI workflow written but never executed (no remote). New tests are characterization tests; mutation check showed they bite. E2E script adds a full-pipeline check to the gate |
| T17 | delegated | 1 | 0 | check.sh pass, 1330 tests, 97.43% | ~570+/0- (incl. 224 docs) | `0d05281`, `510be92` | RED seen before the packaging script. Docs cite OpenLP 3.1.8 source file:line; unverifiable facts are marked in the docs. Found that the plugin loader ignores a custom/portable data path |
| T18 | delegated | 1 | 0 | check.sh pass, 1361 tests, 97.43%; headless with `OPENLP_LANGUAGE=es` OK | ~890+/14- (catalog 399, tests 309) | `dadb0d4` | RED seen (import errors, then 2 widget failures). Catalog is a Python `QTranslator` because plugins cannot add `.qm` files and `lrelease` is absent. Exceeds the 400 heuristic by nature of the catalog. Not reviewed by a native speaker |
| T15 | delegated read-only sdd-security reviewer | 1 | n/a | CLEAR: 0 critical/high, 3 medium, 4 low | 0 | `6f20948` | Findings in `odd/findings/t15-findings.md`; opened T15a-T15c |
| T15a | delegated | 1 | 0 | check.sh pass, 1397 tests, 97.55% | 412+/35- (SEC-003), 167+/30- (SEC-001), 62+/5- (SEC-002) | `bb8209e`, `3209ff2`, `a1fffe4` | RED seen per finding; the ReDoS RED was a hang (regex holds the GIL, pytest-timeout cannot fire). Key now bound to its server origin |
| T15b | delegated | 1 | 1 (watcher flag first version broke 2 deadline tests; caught by the gate) | check.sh pass, 1423 tests, 97.50% | 387+/26- | `f188eb0` | RED 24/26. Covers SEC-004..007 plus two T12c lows |
| T15c | delegated | 1 | 0 | check.sh pass, 1432 tests, 97.50% | 264+/9- code, 60+/2- docs | `24f4701`, `6e1420f` | Plain text boxes/tooltips, `has_search` off, first-use notice, security docs. Nothing filed upstream |
| T15 verify | delegated adversarial verifier | 1 | n/a | CLEAR: 0 critical/high/medium; 2 low, 8 info | 0 | n/a | Gate 1432 passed in a detached worktree; every original T15 repro closed. Findings in `odd/findings/t15d-findings.md`; opened T15d |
| T15d | delegated | 1 | 0 | check.sh pass, 1445 tests, 97.45%; the first gate run died with a segfault in QtWebEngine; two reruns passed | 401+/45- | `dc3d588` | RED: import errors for the new symbols, 5 failing `test_key_origin` tests, and the status-label test failed on the old code. Notice bound to destination in a private file; repair prompt capped; PNG decode weighted by bit depth; stale key dropped instead of blocking. Residuals (data URI IHDR, `localize` cost, two-read key, surrogate echo, Windows ADS) documented, not fixed |
| T19 | inline | 0 | 0 | check.sh pass | docs only | see git log | This table, the summary below, README "Status" and the feature document |

## What the overnight run measured

Window: first commit 2026-10-16 23:13, last code commit 2026-10-17 11:03 (about 12 hours, one orchestrator, no human input during the run).

| Measure | Value |
|---------|-------|
| Backlog tasks | 20 (T01-T20) plus 11 follow-up units opened by checks: T06b, T06c, T07b, T09b, T12b, T12c, T13b, T15a, T15b, T15c, T15d (T20 is an extra task found by the orchestrator) |
| Done / blocked | All done except T14 (AI background images), stopped on purpose for product decisions |
| Commits on the feature branch | 53 (14 `fix`, 12 `feat`, 21 `docs`, plus `test`, `ci`, `chore`, `build`) |
| Tests | 3 (T02/T03) to 1445 at the last gate; about 1,440 added |
| Coverage (gate layers, branch) | 96.2% at T06 to 97.45% at the last gate; the gate floor is 90% |
| Independent verifiers | 10 verifier or review runs: T02/T03, T04-T06, T07-T08, T06b re-verify, T09-T10, T11-T12, T20/T12b, T13, T15 review, T15 verify |
| Verifier outcome | Clean pass 1 (T02/T03); pass with low residuals 1 (T06b re-verify); CLEAR verdict but fixes needed 2 (T15 review, T15 verify: no critical or high); FAIL 6 (T04-T06, T07-T08, T09-T10, T11-T12, T20/T12b, T13) |
| Reopened by a verifier or review | 10 units: T06b, T07b, T09b, T12b, T12c, T13b, T15a-c (the security review) and T15d; T06c came from the T06b re-verification, so 11 follow-ups in all |
| Findings per verifier | T02/T03: 0; T04-T06: 6 (5 bypasses and a regex DoS); T07-T08: 4; T06b re-verify: 2 low; T09-T10: 4; T11-T12: 5; T20/T12b: 8 (1 medium); T13: 5; T15 review: 3 medium, 4 low, info; T15 verify: 10 (2 low, rest info) |
| Self-found rework | 8 tasks had one internal rework round (failing test bug, race, harness bug); the orchestrator's own gate rerun found T20 |

What it shows:

- Green tests did not mean safe: every security-relevant unit that got an independent adversarial verifier came back with findings, and the first real defects were in the sanitizer (T06) and renderer (T07/T08), not in feature code.
- The returns diminished: findings per verifier fell from medium and high severity (T06, T12) to low and info (T15 verify), and the last review found no critical, high or medium issue.
- The cost of verification is high but concentrated: 11 follow-up units against 20 backlog tasks.
- Process faults that mattered: a writer touched the real OpenLP profile once (T03); a leaked test watchdog hid behind a hang (T20); one gate run in three hit an unreproducible QtWebEngine segfault late in the run (T15d), so the gate can be flaky and should be rerun before it is trusted either way.
- Not measured: token or money cost per task (not captured by the run), and the human review time still needed.
