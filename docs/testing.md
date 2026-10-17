# Testing

## Quality gate

```bash
scripts/check.sh
```

Runs `ruff` and the full pytest suite with coverage, using `../openlp/.venv/bin/python` (override with `PYTHON`).
Coverage is measured on `portadas/domain`, `portadas/application` and `portadas/security` only (adapters need Qt and are
covered by integration tests); the minimum is `COVERAGE_MIN`
(default `90`).

The venv needs the dev-only tools `pytest-cov` and `ruff` (`../openlp/.venv/bin/pip install pytest-cov ruff`).
They are not plugin runtime dependencies.

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
