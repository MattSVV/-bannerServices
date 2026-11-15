# bannerServices — Portadas for OpenLP

A personal project with two outcomes:

1. **Product:** *Portadas*, an OpenLP plugin that creates sermon cover slides (title, icon, subtitle, key verse, readings) from HTML/CSS templates or from an AI-designed template, and adds them to the service order.
2. **Experiment:** a public record of **how an AI software factory was designed**. A human acts as product manager and factory builder, AI agents execute the backlog, and the cost of code that actually works is measured.

> This is a personal learning project, not an official OpenLP plugin. It is published as open source so others can study both the plugin and the factory that built it.

## Quick path (end users)

1. If your OpenLP is older than **3.1.8**, upgrade it first: [`docs/upgrade-church.md`](docs/upgrade-church.md) (backup, check, rollback).
2. Install and enable the plugin on Windows, macOS or Linux: [`docs/install.md`](docs/install.md).
3. Releases are zips built by `scripts/package.py`; each comes with a SHA-256 checksum file.

## Quick path (developers)

1. Run OpenLP **3.1.8** from source (see [Development setup](#development-setup)).
2. Link the plugin into OpenLP's community plugins dir: `scripts/dev-install.sh`.
3. Run the quality gate: `scripts/check.sh`.
4. Start OpenLP. A **Portadas** tab appears in the library.

## The product

From OpenLP, the user fills in the sermon data, picks a template (or asks the AI for a custom design), and gets a 1920x1080 cover. The cover is saved in the Portadas library, can be exported as PNG (for example for social media), and can be added to the service right before the sermon.

| Field | Example |
|-------|---------|
| Label | MENSAJE |
| Title (second line accented) | Resistir / *al diablo* |
| Icon | shield with a heart (bundled SVG, upload, or AI-drawn) |
| Subtitle | Firmes en la batalla de la mente… |
| Key verse | Efesios 6:11 |
| Readings | Efesios 6:11-12 · 2 Corintios 10:4-5 · … |

### Two generation modes

| Mode | How it works |
|------|--------------|
| Templates | Built-in HTML/CSS templates. Deterministic, free, and offline. |
| AI (bring your own key) | The user configures a provider (OpenAI, Anthropic, Google Gemini, or any OpenAI-compatible endpoint) with their own API key. The AI creates a brand-new template with creative freedom (layout, colors, typography, decorative SVG), within the sanitizer rules. The text is always injected by our code, escaped. The AI writes no text, with one exception: if you enter only Bible references, it also suggests a title and subtitle (see below). |

### Configuring AI

Open **Settings > Configure OpenLP > Covers**. Pick a provider, optionally type a model name (the box shows the default), and paste your API key (the **Show** button reveals what you are typing, to check the paste). For a local server such as Ollama choose *OpenAI-compatible server* and enter its address (`https://...`, or `http://localhost:11434/v1`). The key is stored in a private file in your OpenLP data folder, not in OpenLP's settings, so exporting your settings never includes it. Press **Save key**: it tests the key with the provider first and saves it only if the test succeeds, otherwise it shows the reason and saves nothing (**OK** never saves a typed key). The field never shows a saved key again; it says "saved", and **Clear** followed by **OK** removes it. **Test connection** asks the provider (in the background) whether the key and model work. Default models were checked against each provider's documentation on 2026-10-17 (OpenAI `gpt-6-luna`, Anthropic `claude-haiku-5-5`, Gemini `gemini-3.5-flash-lite`; the OpenAI-compatible default `llama3.1` is an unverified example, change it to a model your server has). If you change the server address after saving a key (or an imported settings file does), the key is no longer trusted for the new server: **Test connection** and the AI design stop and ask you to enter the API key again in the same tab, naming the server now configured; nothing is sent until you do. A keyless local server with no saved key works as before. When you ask the AI for a design, the cover text and your style hint are sent to the provider you chose; see `docs/security.md`.

### Designing a cover with AI

In the cover editor, type the cover text as usual, optionally describe the style you want (up to 300 characters, for example "warm colours, stained glass"), and click **Design with AI**. The request runs in the background: the button is disabled, the status line says the AI is working, and **Cancel design** stops waiting (the request ends at its next checkpoint and its answer is discarded). When the design arrives, the preview redraws with it, and a note tells you the cover now uses an AI-designed template. The AI designs the look and does not change your text. If the AI also drew an icon, it appears as "Uploaded" in the icon list.

**Only Bible references?** Leave the main title, the highlighted title and the subtitle empty, fill the key verse and/or the readings, and click **Design with AI**. The AI then also suggests a title, an optional highlighted title and a subtitle in the language of the references, and they appear in the normal fields so you can read and edit them before saving; the status line and the note say the text came from the AI. The suggestion must be plain text within the field limits, or it is rejected with a message (the design still applies). If you wrote any of those three fields, the AI writes no text, and text you type while it works is never overwritten. Saving still needs a main title.

Failures are shown on the status line without any key or provider detail: no key saved, an invalid server address, a network error, a request that took too long, or a template that was rejected as unsafe after one correction. Fix the cause in *Settings > Configure OpenLP > Covers* or try again. *Use the selected template instead* (or clicking a built-in template) goes back to a built-in template. *Save* is disabled while a design is running, and closing the editor cancels it. The AI template is stored with the cover and checked again every time it is opened.

### Key design decisions

| Decision | Why |
|----------|-----|
| Target OpenLP **3.1.8** (PyQt5) | Latest stable release. `master` is 4.0 alpha on PySide6. |
| Load as a **community plugin** from `<DataDir>/contrib/plugins/` | Supported by OpenLP's plugin manager since 3.1.0, so no fork is needed. |
| Render with **QtWebEngine** (HTML/CSS → PNG) | Already shipped with OpenLP. Gives the AI full artistic freedom with zero new dependencies. |
| AI returns a template with **placeholders**; our code injects the escaped text | Scripture references and titles must be exact. The AI controls how the text looks, never what it says. |
| AI HTML is **sanitized** and rendered with JS off and network blocked | AI output is untrusted input. |
| **Bring your own key** | The project pays no AI costs, and each church uses the provider it prefers. |
| Runtime deps limited to what OpenLP ships | Packaged OpenLP builds cannot install extra packages. |
| **Spanish** follows OpenLP's language setting, served from a Python catalog | A plugin cannot add `.qm` files to OpenLP, and the Qt compiler is not shipped. See [docs/install.md](docs/install.md). |
| Hexagonal architecture | The domain and use cases are pure Python and tested without Qt. Qt, OpenLP and HTTP live in adapters. |

## The factory experiment

The goal is to learn how to design agent systems that resolve backlog tasks on their own, and to measure what that costs.

| Stage | What happens |
|-------|--------------|
| 1. Product | The human defines the product and decisions with an AI partner (this README). |
| 2. Backlog | Work is broken into tasks: development, security, quality, testing. See [`odd/tasks/portadas-plugin.md`](odd/tasks/portadas-plugin.md). |
| 3. Execution | An orchestrator agent runs Organic Driven Development (ODD): explore → plan → TDD implementation by delegated agents → quality gates → work-unit commits. |
| 4. Measurement | Each task records delegations, rework and gate results in [`docs/factory-log.md`](docs/factory-log.md). |

How this factory was designed, decision by decision:

1. **Concepts before code.** Product flow, data model and AI strategy were settled in conversation before any code existed.
2. **Verify, don't assume.** OpenLP's plugin loader, Qt binding and display engine were confirmed by reading OpenLP's source, not from memory.
3. **A small slice first.** The first task proves the riskiest assumption (external plugin loading) before building on it.
4. **Gates over trust.** Every task closes with tests, lint and a commit. Security and quality are backlog tasks, not afterthoughts.

## Development setup

Tested on Rocky Linux 10.2 with Python 3.12.

```bash
# OpenLP 3.1.8 from source, next to this repo
git clone https://gitlab.com/openlp/openlp.git ../openlp
git -C ../openlp checkout 3.1.8
python3 -m venv ../openlp/.venv
../openlp/.venv/bin/pip install -e "../openlp[test]" websocket-client
# dev-only tools for the quality gate (not plugin dependencies)
../openlp/.venv/bin/pip install pytest-cov pytest-timeout ruff
# dbus-python and PyICU compile from source: on RHEL-family systems run
#   sudo dnf install python3-devel libicu-devel dbus-devel gcc-c++
../openlp/.venv/bin/python ../openlp/run_openlp.py
```

| Path | Purpose |
|------|---------|
| `~/.local/share/openlp/contrib/plugins/` | Community plugins (Linux) |
| `~/.cache/openlp/openlp.log` | OpenLP log (`-l debug` for verbose output) |

## Status

Feature-complete. The overnight factory run built the library tab, the editor with live preview, the three built-in templates, PNG export, service integration, AI-designed templates (bring your own key), the sanitizer and sandboxed renderer, Spanish UI, packaging and the docs, with 1,445 tests at 97% coverage and independent security verification (see [`docs/security.md`](docs/security.md)).

- **AI scope (owner decision, 2026-10-17):** the AI designs HTML/CSS templates only. AI-generated background images (T14) were dropped.
- **Manual checks still pending** (nothing here has been exercised by a human or on another platform):
  - the GUI checklist in [`docs/testing.md`](docs/testing.md) (adding a cover to the real service and showing it live);
  - macOS runs (0.1.1 loads on a Windows church PC with OpenLP 3.1.7, confirmed 2026-11-15; 0.2.0 has not been installed there yet);
  - the CI workflow, which has never run because the repo has no remote yet;
  - a review of the Spanish translation by a native speaker;
  - a live test against a real AI provider (default model ids are unverified).

How the run was executed, including rework and what the verifiers found, is in [`docs/factory-log.md`](docs/factory-log.md). Task list and evidence: [`odd/tasks/portadas-plugin.md`](odd/tasks/portadas-plugin.md).

## Changelog

### Unreleased

- **Fix:** after editing a saved cover, the slide thumbnails showed the new image but the Preview and Live screens kept the old one. OpenLP's display loads images by file URL and can serve a cached picture for a URL it has already seen, and the plugin rewrote the image at the same path. Every save now writes the image under a new file name (the newest three versions are kept, so covers already in the service order still open).

### 0.2.0 (2026-11-15)

- **AI text suggestion:** when the main title, highlighted title and subtitle are all empty and a key verse or readings are given, *Design with AI* also suggests those three texts. They appear in the editor fields for review before saving. If any of them is filled, the AI writes no text, as before. Suggested text goes through the same validation and escaping as typed text.
- **API key setup:** a *Show* toggle reveals the key being typed (never a saved key), and a *Save key* button stores it only after a successful connection test. *OK* no longer saves a typed key; it warns instead.
- **Fix:** the cover editor's form now scrolls, so the AI section is reachable on small screens.
- **Fix:** *Test connection* redacts the typed key in provider errors; a pending *Save key* test is cancelled when the dialog closes; a repaired AI design keeps its suggested text.

### 0.1.1 (2026-11-08)

- **Fix:** the plugin failed to load on the Windows build of OpenLP (`ImportError: cannot import name 'QtSvg' from 'PyQt5'`), because that installer does not bundle the QtSvg module. QtSvg is now optional: without it the icon picker lists icons by name instead of showing thumbnails. Covers still show their icons, since they are drawn with QtWebEngine.

### 0.1.0

- First release: library tab, cover editor with live preview, three built-in templates, PNG export, service integration, AI-designed templates, Spanish UI.

## License

GPL-3.0-or-later, same as OpenLP. See [LICENSE](LICENSE).

## References

- [OpenLP source](https://gitlab.com/openlp/openlp)
- [Latent Space: Zach Lloyd on software factories](https://www.latent.space/p/software-factories)
- [Warp Factories announcement](https://fortune.com/press-releases/warp-launches-warp-factories-automate-software-development-2026-08-18/)
- [Cortex: What is an AI software factory?](https://www.cortex.io/post/what-is-an-ai-software-factory)
- [Paulund: Build factories, not features](https://paulund.co.uk/notebook/ai/software-factory-build-factories-not-features)
