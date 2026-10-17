# Installing Portadas

Portadas is an OpenLP community plugin for **OpenLP 3.1.8**. Installing it means copying one folder, `portadas`, into OpenLP's `contrib/plugins` folder and enabling it. No other software is needed.

Facts below were checked against the OpenLP 3.1.8 source (tag `3.1.8` of `gitlab.com/openlp/openlp`) and are cited as `file:line`. Anything not checked is marked **(unverified)**.

If your church runs an older OpenLP, follow [upgrade-church.md](upgrade-church.md) first.

## 1. Get the release zip

Release zips are named `openlp-portadas-<version>.zip` and come with a `.sha256` file. Check the zip before using it:

| System | Command |
|--------|---------|
| Linux | `sha256sum -c openlp-portadas-0.1.0.zip.sha256` |
| macOS | `shasum -a 256 openlp-portadas-0.1.0.zip` and compare with the `.sha256` file |
| Windows (PowerShell) | `Get-FileHash openlp-portadas-0.1.0.zip -Algorithm SHA256` and compare |

To build the zip yourself from a checkout, run `python3 scripts/package.py` (output goes to `dist/`). The zip holds only the `portadas/` folder (code, templates, icons, fonts, licence), so the same source always gives the same bytes.

## 2. Find OpenLP's data folder

OpenLP looks for community plugins in `<DataDir>/contrib/plugins/`. `DataDir` depends on the system:

| System | DataDir | Source |
|--------|---------|--------|
| Windows | `%APPDATA%\openlp\data` (usually `C:\Users\<you>\AppData\Roaming\openlp\data`) | `openlp/core/common/applocation.py:137-140` |
| macOS | `~/Library/Application Support/openlp/Data` (OpenLP asks the `platformdirs` library for the user data dir and adds `Data`) | `applocation.py:145-149` |
| Linux | `~/.local/share/openlp`, or `$XDG_DATA_HOME/openlp` when that variable is set (the `platformdirs` default) | `applocation.py:145,162-164` |

The `platformdirs` defaults for macOS and Linux come from that library's documentation, not from OpenLP's code **(unverified here)**; the quickest check is to look at where your OpenLP already keeps its `songs` or `themes` folder.

The plugin loader uses exactly this folder (`openlp/core/lib/pluginmanager.py:57-61`), and it looks for files matching `plugins/*/[!.]*plugin.py` under `contrib` (`pluginmanager.py:57`; the `contrib` part is added in `openlp/core/common/__init__.py:146-148`). So the final layout must be:

```
<DataDir>/contrib/plugins/portadas/portadasplugin.py
<DataDir>/contrib/plugins/portadas/templates/...
```

Two cases to know about:

- **Custom data folder** (Settings > Configure OpenLP > Advanced > data path) and **portable mode** (`-p`): covers follow the custom/portable data folder, but the plugin loader still reads `contrib/plugins` from the operating system's default `DataDir` above. This is read from `applocation.py:86` versus `pluginmanager.py:60`; it was not run on a real portable install **(unverified in practice)**. Install the plugin in the default `DataDir`.
- **Sandboxed packages** (Flatpak, Snap, App Store builds) may use another folder **(unverified)**. Start OpenLP with `-l debug` and look in the log (see Troubleshooting) for the line `Attempting to import ... portadas` (`openlp/core/common/__init__.py:153`).

## 3. Install

1. Close OpenLP. Plugins are scanned only while OpenLP starts (`pluginmanager.py:52-61`).
2. Create `<DataDir>/contrib/plugins/` if it does not exist.
3. Unzip the release **into** that folder, so that a `portadas` folder appears there.
   - Linux/macOS: `mkdir -p "<DataDir>/contrib/plugins" && unzip openlp-portadas-0.1.0.zip -d "<DataDir>/contrib/plugins"`
   - Windows: right-click the zip, *Extract All...*, and choose the `contrib\plugins` folder. Check that you did not end up with `plugins\portadas\portadas` (one level too deep).
4. Start OpenLP.

## 4. Enable the plugin

Portadas is installed as **Inactive** (its default status is set in `portadas/portadasplugin.py`; OpenLP lists it as *Inactive* until you enable it).

1. Open **Settings > Manage Plugins** (`openlp/core/ui/mainwindow.py:433`).
2. Select **Portadas** in the list. It shows *(Inactive)*.
3. Tick **Active** (`openlp/core/ui/pluginform.py:130-137`). The change applies at once; no restart is needed.
4. A **Portadas** tab appears in the media library, and **Settings > Configure OpenLP > Covers** appears for AI options.

If Portadas is missing from the list, the plugin was not found or failed to import: see Troubleshooting.

## 4b. Language

Portadas speaks the language OpenLP is set to. It has two languages: English (the source) and Spanish. When OpenLP's language is Spanish (**Settings > Language**, then restart OpenLP, as OpenLP itself asks), every label, button, tooltip, message and error of the plugin appears in Spanish, including the *Automatic* choice when your system is Spanish. Any other language shows English.

How it works, and why it is not a `.qm` file: OpenLP reads translations only from the `.qm` files in its own `i18n` folder (`openlp/core/common/i18n.py`, `LanguageManager.get_translators` at line 220 and `find_qm_files` at line 246) and installs them once at start (`openlp/core/app.py:605-611`). A community plugin cannot add to that folder, and the Qt tool that compiles `.ts` into `.qm` is not part of OpenLP's runtime. The plugin therefore keeps its Spanish texts in a plain Python catalog (`portadas/lib/i18n_es.py`) and, when it loads, installs a small `QTranslator` that answers from it. The plugin's text still goes through OpenLP's `translate()`, so the standard mechanism is used and nothing is patched. Texts that are not in the catalog stay in English. The default cover labels *MENSAJE* and *LECTURAS* are cover content, not interface text, and are the same in every language.

To check it, choose Spanish in OpenLP and restart: the media tab reads **Portadas**. Adding another language means adding a catalog module and mapping its code in `portadas/lib/i18n.py`.

## 5. Where your data lives

| What | Where | Notes |
|------|-------|-------|
| Plugin code, templates, fonts | `<DataDir>/contrib/plugins/portadas/` | Replaced on update, removed on uninstall |
| Covers (`<id>.png` and `<id>.json`) | `<OpenLP data folder>/portadas/` | Follows a custom or portable data folder (`applocation.py:75-90,112-120`) |
| AI key file | `<OpenLP data folder>/portadas/secrets/api-keys` | Owner-only permissions. Never part of OpenLP's settings export. |
| On/off status | OpenLP settings (`portadas/status`) | Included in a settings export |

Back up the `portadas` folder next to your other OpenLP data. Do **not** share the `secrets` folder.

## 6. Update

1. Close OpenLP.
2. Delete `<DataDir>/contrib/plugins/portadas/` (only that folder; your covers are elsewhere, see above).
3. Unzip the new release into `contrib/plugins` as in step 3.
4. Start OpenLP. The plugin keeps its Active status and your covers.

Do not unzip over the old folder: files removed in the new version would stay behind.

## 7. Uninstall

1. Close OpenLP.
2. Delete `<DataDir>/contrib/plugins/portadas/`.
3. Optional: delete `<OpenLP data folder>/portadas/` to remove your covers and the AI key file. Keep it if you may reinstall.

Leaving the status in OpenLP's settings is harmless: a plugin whose files are gone is simply not loaded **(unverified by running; follows from the loader only importing what it finds)**.

## 8. Troubleshooting

**Log file.** OpenLP rewrites its log at every start. Start with `-l debug` for detail (`openlp/core/app.py:292,308-318`).

| System | Log |
|--------|-----|
| Linux | `~/.cache/openlp/openlp.log` (`applocation.py:165-166`) |
| Windows | `%APPDATA%\openlp\openlp.log` (`applocation.py:137-143`: every non-data folder is `%APPDATA%\openlp`) |
| macOS | `~/Library/Application Support/openlp/openlp.log` (`applocation.py:146-151`) |
| Portable | `<portable path>/Other/openlp.log` (`app.py:533-536`) |

Search the log for `portadas`. A line `Failed to import contrib.plugins.portadas...` (`openlp/core/common/__init__.py:159`) comes with the Python error.

**Plugin not in the list.** Check the layout in step 2, that OpenLP was restarted, and that the file `portadasplugin.py` is directly inside `portadas`.

**Covers do not render / blank preview.** Portadas draws covers with QtWebEngine. OpenLP 3.1.8 declares `PyQtWebEngine` as a dependency (`setup.py:115`), but some Linux distribution packages split it out. If OpenLP starts but covers fail, install your distribution's PyQt5 WebEngine package (the name varies, for example `python3-pyqt5.qtwebengine` on Debian-family systems **(unverified)**) and restart.

**No screen (servers, containers, CI).** Run with `QT_QPA_PLATFORM=offscreen`. The repository's `scripts/run-headless.sh` and `scripts/e2e_flow.py` do this to render covers without a display. On a normal desktop you do not need it.

**AI design fails.** The status line gives the reason without revealing your key. Check the key and model in *Settings > Configure OpenLP > Covers*. See [security.md](security.md) for what is sent to the provider.

**Permissions on Linux/macOS.** The key file must be readable only by you. If Portadas reports it as group- or world-accessible, run `chmod 600` on the file it names.
