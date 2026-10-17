# Testing

## Quality gate

```bash
scripts/check.sh
```

Runs `ruff` and the full pytest suite with coverage, using `../openlp/.venv/bin/python` (override with `PYTHON`).
Coverage is measured on `portadas/domain` and `portadas/application` only; the minimum is `COVERAGE_MIN`
(default `0`, raised as those layers grow).

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
- `portadas/domain` and `portadas/application` must not import Qt or OpenLP.
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
