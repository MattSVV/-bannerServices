# Testing

## Quality gate

```bash
scripts/check.sh
```

Runs `ruff` and the full pytest suite with coverage, using `../openlp/.venv/bin/python` (override with `PYTHON`).
Coverage is measured on `portadas/domain`, `portadas/application` and `portadas/security` only (adapters need Qt and are
covered by integration tests); the minimum is `COVERAGE_MIN`
(default `90`).

The venv needs the dev-only tools `pytest-cov`, `pytest-timeout` and `ruff`
(`../openlp/.venv/bin/pip install pytest-cov pytest-timeout ruff`). They are not plugin runtime dependencies.

### Continuous integration

`.github/workflows/ci.yml` (GitHub Actions, Ubuntu 24.04, actions pinned to exact tags) installs the Qt/QtWebEngine
runtime libraries and Xvfb, clones OpenLP 3.1.8 from source next to the checkout (`../openlp`, where `scripts/check.sh`
looks for it), installs it with its `test` extras plus `pytest-cov`, `pytest-timeout`, `ruff` and `websocket-client`,
then runs `scripts/check.sh` and `scripts/run-headless.sh` under `xvfb-run`. `PORTADAS_REQUIRE_RENDER=1` makes a renderer
that cannot start fail the build instead of skipping pixel tests.

**Status: never executed.** This repository has no remote yet, so the workflow has not run anywhere. It was checked only
as YAML (`python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`). Expect to adjust apt package
names or OpenLP's optional dependencies on the first real run. Action tags are pinned but not by commit SHA; pin SHAs
once a remote exists.

### Coverage

The gate measures branch coverage on the pure layers (about 97%). The adapters are exercised by integration tests and
are not part of the gate; their weakest spots are the QtWebEngine renderer's defensive timeouts and the secret store's
OS error paths, which need a failing file system or a stalled web view to reach.

### Hang guards

- `pyproject.toml` sets `timeout = 60` and `timeout_method = "thread"` (pytest-timeout): a test that runs longer than
  60 s dumps every thread's stack and the run aborts. The thread method is used because a signal-based timeout never
  runs while the main thread is stuck inside Qt.
- `scripts/check.sh` wraps pytest in `timeout` (`TESTS_TIMEOUT`, default 600 s; status 124 means it fired).
- `tests/conftest.py` stops the run, naming the test, if a test leaves Qt's event loops dead. Never call
  `QCoreApplication.exit()` or `quit()` in a test (not even from a watchdog timer): pytest-qt runs no
  `QCoreApplication.exec`, so the "quit" flag is never cleared and every later `QEventLoop.exec` returns at once.
  `qtbot.waitUntil` then spins creating signal proxies (about 150 000 in a minute), and destroying them is quadratic:
  that was the intermittent suite hang (T20). Use a timer that closes the object under test instead (see the
  `watchdog` fixture in `tests/test_qt_renderer.py`).

## How tests import the plugin

OpenLP puts `<DataDir>` on `sys.path` and imports `plugins/<name>/<name>plugin.py` under the module name
`contrib.plugins.<name>.<name>plugin` (`extension_loader` and `path_to_module` in `openlp/core/common/__init__.py`).
`tests/conftest.py` builds a temporary data dir with `contrib/plugins/portadas` symlinked to the repo's `portadas/`
package and puts it on `sys.path`, so tests import `contrib.plugins.portadas.portadasplugin` exactly like OpenLP.

Rules that follow from this:

- Inside `portadas/`, use **relative imports**. The package name is `contrib.plugins.portadas`, not `portadas`.
- Tests must not `import portadas` directly: that would load a second copy under another name.
- `portadas/domain` and `portadas/application` must not import Qt or OpenLP. Tests import as `contrib.plugins.portadas.*` (conftest wires the path at import time).
- OpenLP reads `<name>/status` while instantiating a plugin, so the plugin registers a default for it at import time.

## Runtime harness (headless OpenLP)

```bash
scripts/run-headless.sh
```

It links the plugin into a **throwaway** XDG profile (your real OpenLP profile is untouched), starts OpenLP 3.1.8
with `QT_QPA_PLATFORM=offscreen -l debug -e`, waits until the plugin is initialised, stops OpenLP, and prints the
Portadas lines of the log. It exits non-zero if a Portadas error appears or the plugin is not initialised.

Why the profile is pre-seeded (`OpenLP.conf` in the throwaway `XDG_CONFIG_HOME`), otherwise OpenLP blocks on a modal dialog:

| Setting | Avoids |
|---------|--------|
| `core/has run wizard=true` | the first-time language form (`FirstTimeLanguageForm`) |
| `core/application version=3.1.8` and `settings/version=3` | the "Settings are about to be upgraded" message box |
| `portadas/status=1` | the plugin starting `Inactive` (no library tab is created) |

Before OpenLP starts, `scripts/seed_cover.py` creates two covers in the throwaway data dir through the plugin's own use
case and the real renderer; the second uses an uploaded PNG icon, and the script checks the PNG shows up in the render
(sampled red pixels). The harness then requires the log line `Portadas library loaded: 2 cover(s)` and one thumbnail
per cover. Adding to the service needs a visible main window, so it is covered by unit tests
(`tests/test_service_integration.py`) and by the manual checklist below, not by the headless run.

After the library check the harness also runs `scripts/e2e_flow.py` against a second throwaway data dir: for every
built-in template it creates a cover with the production adapters (real QtWebEngine renderer, file repository),
checks the PNG is 1920x1080, lists it in the real library tab, builds the image service item the tab hands to the
service manager and serialises it as the service file would (`ServiceItem.get_service_repr`). It fails on any error
box or Portadas log record at ERROR or above. `tests/test_e2e_script.py` runs the same script inside the pytest gate.
A visible main window is still needed to drop a cover onto the real service manager, so that step stays manual.

Other notes:

- `-e` (`--no-error-form`) stops the exception dialog from blocking on errors.
- A fresh profile creates every plugin database on first start; this takes about a minute on a slow disk, so the
  script waits up to `SECONDS_RUN` (default 120) instead of a fixed time.
- Known OpenLP noise in the log, unrelated to Portadas: `No module named 'uno'` (OpenOffice importers) and
  "Timed out waiting for completion" from the display web view when running offscreen.
- `LOG_COPY=/path/openlp.log scripts/run-headless.sh` keeps the full log.

## Renderer tests (QtWebEngine)

`tests/test_qt_renderer.py` renders real HTML to PNG and asserts pixels (size, background colour, text drawn), the
overflow report, and the sandbox (remote and out-of-bounds URLs blocked, page JavaScript off).

`tests/test_sanitizer_rendered.py` judges the template sanitizer by pixels: hostile pages whose only placeholder is hidden
must render as a flat background once sanitized, and the same pages unsanitized must not (control). See `docs/security.md`.

**Headless works.** QtWebEngine 5.15 renders correctly with `QT_QPA_PLATFORM=offscreen` and no extra flags: no Xvfb,
no `--disable-gpu`, no `--no-sandbox`, no software-GL variables were needed on this machine. What it does need:

| Requirement | Where |
|-------------|-------|
| `QtWebEngineWidgets` imported and `Qt.AA_ShareOpenGLContexts` set before the `QApplication` exists | `tests/conftest.py` |
| `QT_QPA_PLATFORM=offscreen` (conftest defaults it; override with e.g. `xcb` on a desktop) | `tests/conftest.py`, `scripts/check.sh` |
| `QWebEngineView` with `WA_DontShowOnScreen`, resized to the canvas, then `view.grab()` | `adapters/qt_renderer.py` |

Findings worth knowing:

- Page JavaScript can be off while the renderer's own `runJavaScript(..., ApplicationWorld)` still runs (verified on
  Qt 5.15.19). It is used to load fonts, measure text and place a paint canary.
- `runJavaScript` does not await promises, so the renderer polls flags the script sets.
- Painting is asynchronous: grabbing right after "page ready" returned a white image about 1 time in 10. The renderer
  adds a 4 px magenta canary, waits until a grab shows it, removes it, waits until a grab no longer shows it, and
  only then captures. 60 consecutive renders of the reference cover were all correct.
- A render takes about 0.5 s (a fresh off-the-record profile and page per cover).
- The URL interceptor runs on the IO thread; the policy it calls (`security/request_policy.py`) is pure.
- The whole module also passes on a real session (`QT_QPA_PLATFORM=xcb DISPLAY=:0`).
- If rendering cannot start (no usable platform plugin), the module skips with the reason; set
  `PORTADAS_REQUIRE_RENDER=1` (for CI) to fail instead.

Visual evidence: `scripts/render_samples.py` renders every built-in template with the reference cover into
`docs/img/` (`QT_QPA_PLATFORM=offscreen ../openlp/.venv/bin/python scripts/render_samples.py`).

Overflow detection finds fields by CSS class (the placeholder name with `_` turned into `-`: `title-main`, `subtitle`,
`key-verse`...). A field is reported when its text is wider than its box, leaves the canvas, or collides with another
field. Templates that do not use these class names get a render but no overflow report.

## UI tests (pytest-qt)

`tests/test_ai_adapters.py` drives the four AI adapters with a scripted `requests` session (`tests/ai_support.py`): request shape, parsing, retries, error mapping and key redaction, with no network. `tests/test_design_prompt.py`, `tests/test_design_parse_and_use_case.py` and `tests/test_custom_template.py` cover the prompt, the reply parser, the repair round and the stored AI template; `tests/test_background.py` the Qt worker.

`tests/test_edit_form.py` (the cover editor) and `tests/test_mediaitem.py` (the library tab) run the real widgets with
fakes behind the ports (`tests/fakes.py`: an in-memory repository and a renderer the test drives by hand). Message
boxes and file choosers are overridden in the tests, so nothing opens a modal window. The `openlp_env` fixture in
`tests/conftest.py` gives widgets what they need from OpenLP (a `Registry` with a `Settings` backed by a temp file).

`tests/test_edit_form_ai.py` covers the editor's AI mode with a fake `CoverDesigner` that blocks on a gate the test
opens: busy state, double click, cancel, closing mid-request, redacted errors, saving the template, going back to a
built-in template. `tests/test_ai_designer.py` covers the settings-and-key factory.

Things worth knowing:

- A community plugin must register the default shortcuts of its list view itself
  (`shortcuts/listViewPortadas*Item`), otherwise OpenLP raises `KeyError` when it builds the library tab. The media
  item does this when it is created (`QKeySequence` needs a `QApplication`).
- The live preview renders one cover at a time. Edits restart a 400 ms debounce timer; a render that finishes after
  the user kept typing is dropped and a fresh one starts.

## Manual GUI checklist (library tab and editor)

Run OpenLP with the plugin installed (`scripts/dev-install.sh`) and tick each line. Each step says what you should see.
Run it before a release and after any change to the editor, the library tab or the AI mode. The headless run
(`scripts/run-headless.sh`) already proves load, render, library and service-item building; this list covers what only
a visible window shows: dialogs, drag and drop, preview and live output.

- [ ] **Open the tab.** Enable the plugin in *Settings > Plugins* (restart if asked). A **Covers** tab appears in the
  media manager. Empty at first.
- [ ] **Settings tab.** *Settings > Configure OpenLP > Covers* opens. Pick a provider, paste a key, press *OK*; reopen:
  the field says "saved" and never shows the key. *Test connection* answers in the background without freezing the
  window. *Clear* then *OK* removes the key. Check the OpenLP log (`-l debug`) never contains the key.
- [ ] **Create.** Click *New*. Type a main title ("Resistir"), an accent title, a subtitle, a key verse ("Santiago 4:7")
  and two readings, one per line. After about half a second the preview on the right shows the cover. *Save* is
  greyed out while it renders.
- [ ] **Validation.** Type `Xyz 99:99` as a reading: a red message names the line. The preview stops updating until
  you fix it. Clearing the main title and pressing *Save* shows a message box, not a crash.
- [ ] **Overflow.** Type a very long main title: an amber warning appears next to that field.
- [ ] **Templates and icons.** Click each template (thumbnails appear a few seconds after opening) and a few icons;
  the preview follows.
- [ ] **Upload an icon.** *Upload...* with a small PNG: it appears as "Uploaded" and the preview shows it. Try an SVG
  you drew; then a hostile SVG (one with a `<script>`): it is rejected with a message.
- [ ] **AI design.** With a provider and key configured (*Settings > Configure OpenLP > Covers*), type a hint and
  click *Design with AI*: the button greys out and *Cancel design* appears; the preview then redraws with a new look and
  the same text. Click *Cancel design* during a second request: it stops and the previous design stays. With no key,
  the status line says so and nothing is sent. Pick a built-in template: the AI design is dropped.
- [ ] **Save.** *Save* closes the dialog; the cover is in the list with a thumbnail, newest first.
- [ ] **Edit.** Select it, click *Edit* (or the context menu). The fields are filled in; change the title, *Save*:
  the list shows the new title and thumbnail, and there is still only one entry.
- [ ] **Filter.** Type part of a title in the filter box (accents and case ignored): the list narrows.
- [ ] **Export.** Right-click > *Export PNG...*, choose a file. Open it: 1920x1080. Export again to the same file:
  the dialog asks before overwriting.
- [ ] **Preview.** Select a cover and click *Preview* (or double-click): the cover fills the preview screen as a
  single image slide.
- [ ] **Live.** Click *Go Live*: the cover appears on the output screen. Next/previous slide keys do nothing odd.
- [ ] **Add to service.** Click *Add to Service* (or drag the cover onto the service order). A service item with the
  cover's title appears, with the cover as its slide. Select two covers and add them: two service items.
- [ ] **Append.** Drop a cover onto an existing Covers service item and choose *Add to selected item*: the item keeps
  its title and gains a second slide.
- [ ] **Service file.** Save the service (`.osz`), delete the cover from the library, then close and re-open the
  service: the item is still there and its slide shows the cover.
- [ ] **Restart.** Close and reopen OpenLP: the covers, thumbnails and the AI template of an AI-designed cover are
  still there, and the log has no `portadas` error line.
- [ ] **Delete.** Select a cover, *Delete*, answer *No*: nothing happens. Answer *Yes*: it disappears.
