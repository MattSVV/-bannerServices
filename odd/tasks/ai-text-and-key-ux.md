# Feature: AI text suggestion, key setup UX, scrollable editor

- **Locator:** `odd/tasks/ai-text-and-key-ux.md` (Engram mirror: `odd/ai-text-and-key-ux/tasks`, project `bannerservices`)
- **Branch:** `feat/ai-text-and-key-ux` (branched from `main` @ `d488107`)
- **Workflow:** Organic Driven Development (ODD). Implementation requested by the owner on 2026-11-15, on site at the church.
- **TDD:** ON. Source: project feature doc `odd/tasks/portadas-plugin.md`. Runner: `../openlp/.venv/bin/python -m pytest`. Gate: `scripts/check.sh`.
- **RDD:** off (decided by global). Delivery is `disabled/unmanaged` and follows ordinary repository policy.
- **Delivery strategy:** `ask-on-risk`. Forecast is about 600-900 authored lines (tests and the Spanish catalog included). Commits stay on the feature branch; push and PR are the owner's decision.

## Objective

Make the AI path usable at the church:

1. The cover editor's AI section is reachable on small screens.
2. The API key can be shown before saving. It is saved only through an explicit **Save key** button, and only after a successful connection test.
3. When the user enters only verses (key verse and/or readings), the AI suggests the cover text as well as the design.

## Problem and why

- On the church PC (Windows, 100% scaling), the editor dialog is cut off below **Icon**, so **Design with AI** is never visible. The form has no scroll area (`portadas/lib/editform.py:99`, fixed 1180x720).
- The settings tab saves a typed key on the dialog's OK with no test. A wrong key is saved silently, and the masked field gives no way to check what was pasted.
- The owner wants to give only the Bible references and have the AI propose the wording.

## Owner decision (2026-11-15)

This revises the invariant "the AI never writes the cover text" from `odd/tasks/portadas-plugin.md`:

- The AI may **suggest** text only when every free-text field (main title, highlighted title, subtitle) is empty and at least one verse reference is present (key verse or readings).
- If the user wrote any of those fields, the AI writes no text and only designs, as today.
- Suggested text is put into the editor's normal fields, where the user sees and edits it before saving. It goes through the same validation, length limits and escaping as typed text. The AI never writes into the template directly, and verse references stay as the user typed them.

## Scope

- **In:** editor scroll area; settings tab show/hide toggle, **Save key** button gated on a successful test, OK no longer saves an untested key; AI text suggestion for empty text fields; Spanish catalog entries; README and `docs/security.md` updates; tests.
- **Out:** release, version bump, push and PR (owner's decision); full verse text lookup (covers still show references only).

## Constraints

- Runtime dependencies stay within what OpenLP 3.1.8 ships.
- UI strings go through `translate()` with Spanish entries in `portadas/lib/i18n_es.py` (the i18n completeness test enforces it).
- No key in logs, errors or UI after saving. The show toggle only reveals the text currently typed in the field, never a stored key.
- Suggested text is untrusted model output: plain text only, control and invisible characters rejected, per-field length limits enforced, rendered through the existing escaping path.

## Tasks

| ID | Area | Task | Route |
|----|------|------|-------|
| A1 | DEV/TEST | Editor form column inside a `QScrollArea`, so the AI section is always reachable; a test that the design button is inside the scrollable area | delegated direct writer (writer trigger: shared run with A2/A3) |
| A2 | DEV/SEC/TEST | Settings tab: show/hide key toggle (typed text only); **Save key** button that runs the connection test and saves only on success; failure shows the reason and saves nothing; OK no longer saves a typed-but-unsaved key and warns instead; Clear unchanged; Spanish entries; docs | delegated direct writer (writer trigger: settingstab, i18n, tests, docs) |
| A3 | DEV/SEC/TEST | AI text suggestion: the main title is no longer required when designing with only verse references; the request asks for suggested text only when the free-text fields are empty; the reply's text is validated and filled into the editor fields; when any text exists, no text is requested or applied; Spanish entries; README and `docs/security.md` | delegated direct writer (writer trigger: domain, application, adapters, editor, tests, docs) |

- [x] A1
- [x] A2
- [x] A3

## Acceptance criteria

- A1: with the dialog at 1180x600, the **Design with AI** button can be scrolled into view.
- A2: a failed test never writes the key store; a successful test followed by save writes it once; OK with an unsaved typed key writes nothing and warns; the toggle switches the echo mode of the typed field only.
- A3: with only readings filled, **Design with AI** sends a request that asks for text, and the suggested title, highlighted title and subtitle appear in the fields; with any free-text field filled, the request asks for no text and the fields are unchanged; invalid suggested text (too long, control characters, markup) is rejected with a message and the design still applies or fails closed; saving still requires a main title.
- Every task: `scripts/check.sh` passes (ruff, pytest, coverage at least 90%).

## Progress

| Task | Status | Commit | Evidence |
|------|--------|--------|----------|
| A1 | done | 6196f75 | RED: new scroll-area test failed (no `form_scroll_area`). GREEN: tests/test_edit_form.py 32 passed. Gate: 1455 passed, coverage 97.45%; the only failure is `test_t15b_hardening::test_many_distinct_css_problems_cost_linear_time_and_fail_closed` (2.0 s timing assert), which also fails on the untouched base under `--cov` in the full run and passes alone (environmental, pre-existing). Route: delegated direct writer. |
| A2 | done | c13b492 | RED: 12 new/changed settings-tab tests failed (no `save_key_button`/`show_key_button`, OK still stored a typed key). GREEN: test_settings_tab + test_key_origin + test_i18n 94 passed. Gate: 1465 passed, coverage 97.45%; same single pre-existing timing failure as A1. Route: delegated direct writer. |
| A3 | done | 77a7675 | RED: new prompt, parse/use-case and editor tests failed at collection (no `application/design_text`). GREEN: 103 + 36 targeted tests passed. Gate: `scripts/check.sh` fully passed, 1510 passed, coverage 97.51% (the t15b timing test passed this run). Route: delegated direct writer. |
| A4 | done | 50721c1 | RED: 5 new tests failed (typed-key Test connection not registered, OK did not cancel a running Save key test, field cleared after a different typed key, repair prompt without `suggested_text`). GREEN: settings tab, design parse/use-case and design prompt tests 138 passed except `test_defaults_are_loaded`, which fails when run alone on the base too and passes in the full run. Gate: `scripts/check.sh` 1515 passed, coverage 97.52%, one failure: the known t15b timing test, which passes alone (0.70 s). L3 cancel path: OpenLP `reject()` calls `cancel()`, which calls `load()`, which already cancels the test (now pinned by a test). Route: delegated direct writer. |

## Verification

- Review assessment (`gentle-ai review assess`, RDD off): **high** (security doc and editor process signals, 1067 changed lines), so an independent verifier ran.
- Orchestrator spot check: `scripts/check.sh` 1509 passed, 1 failed (the timing test below; passes alone in 0.65 s), coverage 97.51%.
- Independent verifier (read-only): no high or medium findings; 258 focused tests passed. Low findings, open:
  - L1: Test connection with a typed key does not `register_secret` (Save key does), so a provider error echoing the key in an unrecognised form could reach the result label.
  - L2: the repair-round prompt (`outcome.raw`) omits `suggested_text`, so a repaired design may arrive without suggested text (safe failure).
  - L3: OK while a Save key test runs does not cancel it; the tested key may still be stored after the dialog closes.
  - Info: a successful save clears the field even if a new key was typed meanwhile; a suggestion computed for old verses still applies if verses changed mid-design.
- `test_settings_tab.py::test_defaults_are_loaded` fails when run in isolation on `main` too (machine settings dependent, unconfirmed).

## Next step

Owner decision (2026-11-15): fix L1-L3, then release v0.2.0 (merge to `main`, tag, GitHub release with zip and checksum).

- [x] A4 (fix verifier lows L1-L3) — route: delegated direct writer
- [ ] R1 (release v0.2.0: version bump, changelog, install doc, merge to main, tag, GitHub release) — route: inline, orchestrator Owner decides push and PR. Note: `test_t15b_hardening::test_many_distinct_css_problems_cost_linear_time_and_fail_closed` is timing-sensitive (2.0 s) and flaked under `--cov` in two earlier full runs, also on the untouched base.
