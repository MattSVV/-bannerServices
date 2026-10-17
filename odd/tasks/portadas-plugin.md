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
- [x] T06b (reopened security fix)
- [x] T07b (reopened renderer/repository hardening)
- [x] T09
- [x] T10
- [x] T06c (low-severity sanitizer residuals)
- [x] T11
- [x] T09b (editor defects from verification)
- [x] T20 (intermittent test-suite hang, found by orchestrator)
- [x] T12b (AI adapter hardening, findings in `odd/findings/t12b-findings.md`)
- [x] T12
- [x] T13
- [ ] T14 (blocked: open product/security decisions, see Progress table; nothing implemented)
- [ ] T15
- [x] T16
- [x] T17
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
| T08 | done | `b038b4b` | RED `...application.create_cover` missing, GREEN. Orchestrator spot check: `scripts/check.sh`, 533 passed, coverage 96.37%. Independent verifier: sandbox held 29 network vectors and all file-escape vectors; **2 hangs + soft timeout + orphan PNG loss** → T07b opened. |
| T06b | done | `b955cb3` | Confirmed bypasses in `portadas/security/css_policy.py`: comment markers inside strings, escaped `\/*`, escaped quote in `content`, `list-style` strings, `<ol>` numbering, and super-linear scripture regex. Reason: an independent adversarial verification rendered the bypasses in real QtWebEngine. Fix: CSS Syntax L3 tokenizer + allowlist, `<ol>` removed, forced `list-style:none`, bundled fonts only, linear scripture parser with caps. RED 41+15 failing tests, then GREEN. Orchestrator spot check: 801 passed, 97.04%. Re-verification: all original payloads closed; 170 new CSS payloads and 4.42M fuzz runs gave 0 audit failures. 2 low residuals → T06c. |
| T07b | done | `44d6c35` | Reason: independent T07/T08 verification. Fixed: `render()` hang after `close()`, FIFO hang (`O_NONBLOCK`), canvas cap plus post-grab deadline check, orphan PNG kept, no paths in user errors, JSON as commit marker, page deleted before profile. RED shown for each, then GREEN. Orchestrator spot check: 816 passed, 97.04%. Residual: soft render-time bound (documented). |
| T09 | done | `fa9eb62` | RED: ImportError/ModuleNotFoundError plus 21 failing media item tests, then GREEN 913. Library tab, editor with debounced live preview, icon upload (SVG strict reject; PNG ≤96 KB wrapped as data-URI `<image>`, allowed only by `sanitize_svg(allow_png_image=True)`, never for AI). |
| T10 | done | `aeae46b` | RED 18 failed with a stub, then GREEN 934. Image service items; reopening a service after the cover is deleted is tested. Runtime: `scripts/run-headless.sh` exit 0, `Portadas library loaded: 2 cover(s)`, 0 Portadas errors. Orchestrator spot check: 934 passed. GUI add-to-service/live is N/A headless; covered by the manual checklist in `docs/testing.md`. Independent verifier: upload and service paths held; **re-entrant Save duplicates covers, unsanitised picker SVG can hang, form leak, unbounded PNG decode** → T09b. |
| T06c | done | `78996f6` | RED 17/29, then GREEN. `-webkit-line-clamp` dropped; `U+` unicode-range tokenized and refused; attribute values reject bare `(`/`:`. |
| T11 | done | `8c0b962` | RED: ModuleNotFoundError ×4, then GREEN 1059. Secrets in `portadas/secrets/api-keys` (dir 0700, file 0600, atomic, DPAPI on Windows, mocked test), never in QSettings; log redaction filter; settings tab. Runtime: `Portadas settings tab created`, 0 errors. Orchestrator spot check: 1059 passed. Default model ids unverified → T12. |
| T09b | done | `66fa62e` | RED 13/14, then GREEN 1074. Save re-entrancy guard and stable id, icon sanitized before QtSvg, form deleteLater, PNG pixel cap before decode, PNG chunk/CRC/IEND check, `\A...\Z` id patterns. |
| T12 | done | `9a21107` | Weak RED (import errors), then GREEN 1241, 97.2%. Port `CoverDesigner`, `DesignCoverWithAI` (one repair round), adapters for OpenAI, Anthropic, Gemini (key in header) and OpenAI-compatible; redirects refused; retries bounded; async test connection. Defaults the writer checked against provider docs on 2026-10-17: `claude-haiku-5-5`, `gpt-6-luna`, `gemini-3.5-flash-lite` (OpenAI JSON mode unconfirmed). No live provider test (no keys). Headless OK. |
| T20 | done | `8fe4dc5` | Root cause: a leaked 15 s `QCoreApplication.exit` watchdog killed later `QEventLoop`s. 15/15 loop runs green. Orchestrator spot check: `scripts/check.sh` = 1270 passed, coverage 97.28%, all checks passed. Route: delegated direct writer; verifier pending. |
| T12b | done | `ed06c00` | AI adapter hardening: total deadlines enforced, proxy env ignored, template depth bounded (findings in `odd/findings/t12b-findings.md`). Same orchestrator spot check as T20 (1270 passed, 97.28%). Route: delegated direct writer; verifier pending. |
| T13 | done | `2190cc5` | RED: `ModuleNotFoundError ...lib.ai_designer` plus 17 failing editor tests (`hint_edit` etc. missing), then GREEN 70 focused tests; full gate `scripts/check.sh`: 1294 passed, coverage 97.28%, all checks passed; headless harness OK (0 Portadas errors). Editor AI mode: style hint, *Design with AI* (background job, busy state, *Cancel design*), template and icon applied through `DesignedCover.apply_to`, redacted errors, re-entrancy and late-callback guards, *Save* disabled while designing, picking a template drops the design. `lib/ai_designer.make_designer` wires settings and secret store to `create_designer`; `PortadasServices.designer_factory`. Route: delegated direct writer. No live provider test (no keys). |
| T12c | done | `53b51d1` | Reopened from T12b by independent verification (`odd/findings/t12c-findings.md`). RED: `tests/test_ai_deadline.py` body and header trickle hung until the 12 s test timeout on the old code; 3 secret-store tests failed. GREEN: 5 deadline tests (real local socket server, budget 2 x 0.5 s) plus 3 store tests. Fix: per-attempt watcher thread shuts down the attempt's sockets (tracked via a urllib3 pool subclass) at the deadline or on cancel; backoff uses `cancellation.wait`; untrusted key file is moved to an owner-only `api-keys.corrupt` backup; chmod OSError is a SecretStoreError; conftest guard message names this or an earlier test. By design, documented in `docs/security.md`: lock contention, single `.corrupt` backup. Residual: DNS and connect phase are outside the budget (documented). Gate: `scripts/check.sh` 1302 passed, 97.18%, all checks passed. Route: delegated direct writer (write trigger: 9 files). Verifier pending. |
| T13b | done | `c59044b` | Reopened from T13 by independent verification (`odd/findings/t13b-findings.md`): unexpected factory errors escaped the slot, status label rendered AI text as rich text, a template pick during a design was overridden when the design landed (and a re-click kept the design), an AI icon destroyed the uploaded one. RED: 6 new editor tests and the renderer-interrupt test failed. GREEN: 92 focused tests; `scripts/check.sh` 1309 passed, 97.18%, all checks passed. Fix: `except Exception` logs only the type name and shows a fixed message; `Qt.PlainText` on status and message labels; template pick/re-click cancels the job and drops the design; the icon before the design is restored by *Use the selected template instead* unless the user chose another since; `QtCoverRenderer.render` aborts its job when the loop is ended from outside (T12c finding 7). Residual: error text echoing an unregistered secret (finding 5) is unchanged by design. Route: delegated direct writer; verifier pending. |
| T16 | done | `8c2b261`, `2e94ea8`, `d25245d` | Route: delegated direct writer (write trigger: tests, scripts, workflow, docs). Coverage (branch, gate layers) 97.28% -> 97.43%; weakest were `cancellation` 88% and `request_policy` 90%: added 14 behavior tests (cancellation, malformed URL, cross-drive roots, failed delete, Anthropic refusal/no content). They characterise existing behavior; a mutation (`except ValueError` -> `KeyError` in `request_policy`) made 2 of them fail. E2E: `scripts/e2e_flow.py` (3 built-in templates -> 1920x1080 cover -> library tab -> image service item -> `get_service_repr`, fails on any Portadas ERROR record), run by `scripts/run-headless.sh` (exit 0, `E2E OK`, 0 Portadas errors) and by `tests/test_e2e_script.py` (positive and negative). CI: `.github/workflows/ci.yml` (OpenLP 3.1.8 from source with test extras, xvfb, `check.sh`, headless run), YAML-validated only, **never executed (no remote)**. Manual checklist gained Settings tab and Restart steps. Gate: `scripts/check.sh` 1321 passed, 97.43%, all checks passed. |
| T17 | done | `0d05281`, `510be92` | Route: delegated direct writer (write trigger: script, test, 3 docs). TDD ON, runner `../openlp/.venv/bin/python -m pytest`: RED observed (`tests/test_package_script.py` errored, script missing), then GREEN 9 passed. `scripts/package.py` builds `dist/openlp-portadas-<version>.zip` (version from `pyproject.toml`) with only `portadas/` + `portadas/LICENSE`, no caches/`.pyc`/dotfiles/symlinks, sorted entries, fixed 1980-01-01 timestamp and 0644 mode, byte-identical on rebuild, plus `<zip>.sha256` in `sha256sum` format. Tests also extract the zip into a fake `DataDir/contrib/plugins` and import `contrib.plugins.portadas.portadasplugin` in a subprocess. `docs/install.md` (Windows/macOS/Linux data dirs cited to `applocation.py`, `pluginmanager.py`; enable via Settings > Manage Plugins; update, uninstall, data locations, troubleshooting) and `docs/upgrade-church.md` (version check, settings export, data backup, install, verification, rollback) written from OpenLP 3.1.8 source; README gained "Quick path (end users)". Finding: the community plugin loader reads the OS default `DataDir` (`pluginmanager.py:60`) while covers follow a custom/portable data path, documented. **Unverified, marked in the docs:** `platformdirs` defaults on macOS/Linux, native settings storage location, Flatpak/Snap paths, WebEngine distro package names, 3.1.8 release notes (CHANGELOG stops at 3.1.3), whether any old OpenLP version migrates cleanly, plugin removal with stored Active status. Gate: `scripts/check.sh` 1330 passed, 97.43%, all checks passed (twice). |
| T14 | blocked | | Not implemented on purpose; needs the user's decisions first (see Next step). |

## Accepted changes

- `Cover.readings_label` (default "LECTURAS") plus the `{{readings_label}}` placeholder. Reason: the text guarantee forbids hard-coded visible text, so the static heading must be a placeholder.
- The sanitizer uses the stdlib `html.parser` with an allowlist rebuild instead of lxml or bs4. This is fewer dependencies, which is fine.
- OFL fonts are bundled (Playfair Display, Outfit, about 690 KB) in `portadas/assets/fonts/`.
- Renderer: headless works with `QT_QPA_PLATFORM=offscreen` plus `AA_ShareOpenGLContexts`, with a canvas canary against the white-frame race. Each render takes about 0.5 s.
- Repository: `png_path(id)` instead of a thumbnail cache. Uploaded icons are not supported yet (gap for T09).
- Overflow detection relies on field CSS class names (`docs/templates.md`), so AI templates must use them.
- `MAX_INLINE_SVG` raised to 140,000 characters for embedded PNG icons. Template thumbnails load lazily, and saving blocks for about 0.5 s (possible follow-up).
- AI templates are stored as `Cover.custom_template_html` (additive JSON key, schema 1, re-sanitized on load and on compose). `MAX_JSON_BYTES` is 512 KB. A bad AI icon is dropped after its repair round instead of failing the design.
- Cross-chapter ranges (`Juan 3:16-4:2`) are rejected for now. This is a possible follow-up.

## Findings carried forward

- OpenLP imports the plugin as `contrib.plugins.portadas.portadasplugin`. Internal imports are relative. `tests/conftest.py` replicates this with a temp data dir.
- Headless runs need a pre-seeded throwaway profile (`scripts/run-headless.sh`, `docs/testing.md`).
- ~~Risk for T07: offscreen QtWebEngine~~ resolved in T07.
- During T03 the writer's first unisolated run touched the user's real OpenLP profile. It created a backup conf and data dirs, and installed the dev symlink `~/.local/share/openlp/contrib/plugins/portadas`. This is harmless, and the user should know.

## Next step

T13 is done. T14 is blocked on product/security decisions that must not be guessed:

1. **Where a generated image lives and how a template references it.** The only allowed reference today is `../../assets/backgrounds/<file>`, which resolves inside the plugin package (`portadas/assets/backgrounds/`), not writable in a packaged install and the wrong place for per-cover user data. Options: (a) a data dir `<DataDir>/portadas/backgrounds/<cover id>.jpg` plus a fixed `{{background}}` placeholder that our code expands to a `file:` URL, which widens the renderer's allowed roots by one directory and changes the sanitizer URL grammar; (b) embed as a `data:` URI, which needs raising `MAX_CUSTOM_TEMPLATE` / JSON limits (a 1080p JPEG is far above 150 KB).
2. **Provider and model ids for image generation** (OpenAI images, Gemini) are not verified; they need a docs check and a cost statement. Confirm that image generation is wanted at all (extra cost per design, the cover text goes in the prompt, risk of unsuitable imagery on a church screen) and whether the existing settings checkbox *Generate AI background images* is the only consent.
3. **Lifecycle:** delete the image with the cover; regenerate on edit or reuse.

Then T15-T19. Also ask the user to confirm the 6 overnight assumptions and the chain strategy (`stacked-to-main` or `feature-branch-chain`).
