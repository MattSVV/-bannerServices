# Feature: Portadas plugin for OpenLP

- **Locator:** `odd/tasks/portadas-plugin.md` (Engram mirror: `odd/portadas-plugin/tasks`, project `bannerservices`)
- **Branch:** `feat/portadas-plugin` (branched from `main` @ `0cd3e08`)
- **Workflow:** Organic Driven Development (ODD), overnight autonomous run authorized by the user on 2026-10-16
- **TDD:** ON. Source: README plan ("issue → spec → TDD implementation → review → quality gates → PR"). Runner: `../openlp/.venv/bin/python -m pytest` (pytest + pytest-qt from OpenLP 3.1.8 test extras)
- **RDD:** off (decided by global). Delivery is `disabled/unmanaged` and follows ordinary repository policy.
- **Delivery strategy:** `ask-on-risk`. The forecast exceeds 400 authored lines. There is no git remote yet, so PR slicing is deferred: the chain strategy question goes to the user in the morning. Slice boundaries are recorded below as commits accumulate.

## Objective

Build the complete "Portadas" OpenLP plugin. It creates sermon cover slides (label, title, icon, subtitle, key verse, readings) from built-in HTML/CSS templates or from an AI-designed template. It renders them to PNG, keeps them in their own library tab, and adds them to the service order.

## Problem and why

The church currently builds sermon covers by hand, outside OpenLP. The project is also a personal software-factory experiment: the backlog below is the factory's raw material, and how it is executed (cost, rework, gate pass rate) is measured.

## Scope

- OpenLP **3.1.8** (PyQt5, QtWebEngine). The plugin is loaded as a community plugin from `<DataDir>/contrib/plugins/portadas/`, with no fork of OpenLP.
- Two modes: **templates** (deterministic) and **AI** (bring-your-own-key, provider-agnostic).
- The AI designs an HTML/CSS template with placeholders. The text is always injected by our code, escaped, and never written by the AI.
- Optional AI-generated background image (no text) for providers that support image generation.
- Library tab, editor with live preview, add to service, PNG export (social media).

## Constraints

- Runtime dependencies are limited to what OpenLP 3.1.8 already ships (PyQt5 + QtWebEngine, requests, Mako, lxml, beautifulsoup4, platformdirs, SQLAlchemy). Packaged OpenLP builds cannot `pip install` extra packages.
- The license must be GPL-3.0-or-later, because the plugin imports GPL OpenLP code.
- Hexagonal layout: pure-Python domain and application layers (testable without Qt), ports for renderer, AI provider, repository and secret store, and adapters for Qt, OpenLP and HTTP.
- Artifacts (code, comments, UI strings, docs) are in English. UI strings go through OpenLP `translate()`; a Spanish translation is a separate task.
- No secrets in logs, repo, or plain OpenLP settings exports.

## Overnight assumptions (to confirm with the user)

These are product defaults chosen so the overnight run does not block. Each one is reversible.

1. Covers show verse **references only**, as in the reference design, not full verse text. No Bible lookup is needed.
2. Output is a 1920x1080 PNG, stored in `<DataDir>/portadas/`, with JSON metadata.
3. There are 3 built-in templates. The first replicates the reference design "Noche dorada" (dark navy and gold).
4. The icon is chosen from a bundled SVG set (hand-made, license-clean) or uploaded by the user (SVG/PNG). An AI template may draw its own inline SVG icon.
5. AI providers: OpenAI, Anthropic, Google Gemini, and any OpenAI-compatible endpoint (custom base URL, e.g. Ollama or OpenRouter). Image backgrounds use OpenAI or Gemini.
6. The API key lives in a dedicated per-user file with `0600` permissions, outside OpenLP settings exports. It is never logged and is masked in the UI. The OS keyring is not used because it is not in the dependency budget.

## Tasks

Legend: **[DEV]** development · **[SEC]** security · **[QA]** quality · **[TEST]** testing · **[DOC]** docs

| ID | Area | Task | Route |
|----|------|------|-------|
| T01 | DOC | Repo bootstrap: README (personal AI-engineering factory project), GPL license, `.gitignore`, feature doc | inline |
| T02 | QA | Dev tooling and quality gates: `pyproject.toml` (pytest, coverage, flake8/ruff config), `scripts/check.sh`, `scripts/dev-install.sh` (symlink into contrib), `conftest.py` | delegated writer |
| T03 | DEV/TEST | Spike: minimal plugin skeleton (Plugin + empty MediaManagerItem "Portadas") loads from contrib in OpenLP 3.1.8 | delegated writer |
| T04 | DEV/TEST | Domain: `Cover` model, invariants, scripture reference parser/validator (Spanish book names, ranges, `·` lists) | delegated writer |
| T05 | DEV/SEC | Safe template engine (escaped placeholders, no Mako for untrusted input), template manifest, 3 built-in templates, bundled SVG icon set | delegated writer |
| T06 | SEC/TEST | HTML/CSS sanitizer for AI templates: allowlist, no script, event handlers or external URLs, size limits; tests against malicious payloads | delegated writer |
| T07 | DEV/SEC | Renderer adapter: offscreen QtWebEngine HTML→PNG 1920x1080, JS disabled, network blocked by an interceptor, text-overflow detection | delegated writer |
| T08 | DEV/SEC | Cover repository: save/list/delete/export PNG + JSON in DataDir, path-traversal safe | delegated writer |
| T09 | DEV | Library tab UI: list with thumbnails, new/edit/delete, editor dialog (fields, template picker, icon picker/upload, live preview) | delegated writer |
| T10 | DEV/TEST | Service integration: add cover to the service as an image item, preview/live, drag and drop | delegated writer |
| T11 | DEV/SEC | Settings tab and secret store: provider, model, base URL, masked API key, test connection, `0600` key file, log redaction | delegated writer |
| T12 | DEV/TEST | AI port + provider adapters (OpenAI, Anthropic, Gemini, OpenAI-compatible): prompt builder, response parsing, timeouts/retries, background thread; mocked-HTTP tests | delegated writer |
| T13 | DEV | AI mode in the editor: generate design → sanitize → preview → save | delegated writer |
| T14 | DEV | Optional AI background image (OpenAI images / Gemini), referenced by the template as a local asset | delegated writer |
| T15 | SEC | Security review: threat model (`docs/security.md`), dependency and secret audit, independent `sdd-security` pass, fix confirmed findings | delegated reviewer + writer |
| T16 | QA/TEST | Quality hardening: coverage threshold, manual E2E checklist (`docs/testing.md`), CI workflow (GitHub Actions + xvfb) ready for when a remote exists | delegated writer |
| T17 | DEV/DOC | Packaging and install: release zip, install docs for Linux/Windows/macOS contrib paths, church upgrade guide to 3.1.8 | delegated writer |
| T18 | DEV | i18n: Spanish translation of UI strings | delegated writer |
| T19 | DOC | Factory log: per-task metrics (delegations, rework, gate results) in `docs/factory-log.md` | inline |

Order: T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 → T12 → T13 → T14 → T15 → T16 → T17 → T18 → T19 (T19 is updated continuously).

## Checklist

- [x] T01
- [x] T02
- [x] T03
- [x] T04
- [x] T05
- [x] T06
- [x] T07
- [x] T08
- [ ] T06b (reopened security fix, see below)
- [ ] T09
- [ ] T10
- [ ] T11
- [ ] T12
- [ ] T13
- [ ] T14
- [ ] T15
- [ ] T16
- [ ] T17
- [ ] T18
- [ ] T19

## Acceptance criteria

- The plugin loads in OpenLP 3.1.8 from the contrib dir, and a "Portadas" tab appears in the library.
- A cover can be created from each built-in template, rendered to PNG, saved, listed, exported and added to the service.
- With a configured provider and key, the AI mode produces a sanitized template. The rendered text exactly equals the user input.
- AI-produced HTML cannot run JS, load remote resources, or escape the placeholder text.
- The API key never appears in logs, in exported settings, or in the repo.
- `scripts/check.sh` passes: lint plus the full pytest suite, with a coverage threshold on domain and application.

## Applicable checks

- Per task: focused pytest for the unit, then `scripts/check.sh` once it exists (from T02 onward).
- Runtime harness: launch OpenLP 3.1.8 headless (`QT_QPA_PLATFORM=offscreen`) with the plugin symlinked, then inspect `~/.cache/openlp/openlp.log` for the plugin load and any errors.

## Progress and evidence

| Task | Status | Commit | Evidence |
|------|--------|--------|----------|
| T01 | done | `da600a0` | Structural readback of README, LICENSE (GPL-3.0 copied from OpenLP), `.gitignore`. Route: inline (1 mechanical doc unit). |
| T02 | done | `aee17fc` | `scripts/check.sh`: ruff OK, 3 passed, coverage gate configurable (`COVERAGE_MIN`). Route: delegated writer (write trigger: 5 files). Assess tier: high (shell scripts, exec mode). Independent verifier: 6/6 PASS, no defects. |
| T03 | done | `33fc722` | RED `ModuleNotFoundError contrib.plugins.portadas.portadasplugin`, then RED `KeyError 'portadas/status'`, then GREEN 3 passed. Runtime: `scripts/run-headless.sh`, exit 0, log `Loaded plugin <class 'contrib.plugins.portadas.portadasplugin.PortadasPlugin'>`, `Initialisation Complete for portadas`. Orchestrator spot check: `scripts/check.sh`, all checks passed. |
| T04 | done | `08bc47c` | RED `ModuleNotFoundError ...domain.cover`, GREEN 102 tests. Route: delegated writer (shared T04-T06). |
| T05 | done | `66fafe4` | RED `ModuleNotFoundError ...application.icon_catalog`, GREEN 173 tests. Visual check: `noche-dorada` matches the reference design. |
| T06 | done | `cce22a7` | RED `ModuleNotFoundError ...security.html_policy`, GREEN 350 total. Orchestrator spot check: `scripts/check.sh`, 350 passed, coverage 96.16% (gate 90%). Assess tier: high (3143 lines, hot_path). Adversarial verifier: **5 confirmed CSS/text bypasses + regex DoS** → T06b opened. |
| T07 | done | `4b5df9c` | RED `ModuleNotFoundError ...qt_renderer`, GREEN. 26 renderer tests run offscreen (no skips); 60-render stress test had 0 bad images; PNGs in `docs/img/` (noche-dorada pixel `#0e1422`). A local HTTP server saw 0 hits for remote requests. |
| T08 | done | `b038b4b` | RED `...application.create_cover` missing, GREEN. Orchestrator spot check: `scripts/check.sh`, 533 passed, coverage 96.37%. Independent verifier running. |
| T06b | reopened | | Confirmed bypasses in `portadas/security/css_policy.py`: comment markers inside strings, escaped `\/*`, escaped quote in `content`, `list-style` strings, `<ol>` numbering, and super-linear scripture regex. Reason: an independent adversarial verification rendered the bypasses in real QtWebEngine. |

## Accepted changes

- `Cover.readings_label` (default "LECTURAS") plus the `{{readings_label}}` placeholder. Reason: the text guarantee forbids hard-coded visible text, so the static heading must be a placeholder.
- The sanitizer uses the stdlib `html.parser` with an allowlist rebuild instead of lxml or bs4. This is fewer dependencies, which is fine.
- OFL fonts are bundled (Playfair Display, Outfit, about 690 KB) in `portadas/assets/fonts/`.
- Renderer: headless works with `QT_QPA_PLATFORM=offscreen` plus `AA_ShareOpenGLContexts`, with a canvas canary against the white-frame race. Each render takes about 0.5 s.
- Repository: `png_path(id)` instead of a thumbnail cache. Uploaded icons are not supported yet (gap for T09).
- Overflow detection relies on field CSS class names (`docs/templates.md`), so AI templates must use them.
- Cross-chapter ranges (`Juan 3:16-4:2`) are rejected for now. This is a possible follow-up.

## Findings carried forward

- OpenLP imports the plugin as `contrib.plugins.portadas.portadasplugin`. Internal imports are relative. `tests/conftest.py` replicates this with a temp data dir.
- Headless runs need a pre-seeded throwaway profile (`scripts/run-headless.sh`, `docs/testing.md`).
- ~~Risk for T07: offscreen QtWebEngine~~ resolved in T07.
- During T03 the writer's first unisolated run touched the user's real OpenLP profile. It created a backup conf and data dirs, and installed the dev symlink `~/.local/share/openlp/contrib/plugins/portadas`. This is harmless, and the user should know.

## Next step

T06b security fix (writer). In parallel, an independent verifier for T07/T08. Then T09 + T10 (UI and service).
