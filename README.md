# bannerServices — Portadas for OpenLP

A personal project with two outcomes:

1. **Product:** *Portadas*, an OpenLP plugin that creates sermon cover slides (title, icon, subtitle, key verse, readings) from HTML/CSS templates or from an AI-designed template, and adds them to the service order.
2. **Experiment:** a public record of **how an AI software factory was designed**. A human acts as product manager and factory builder, AI agents execute the backlog, and the cost of code that actually works is measured.

> This is a personal learning project, not an official OpenLP plugin. It is published as open source so others can study both the plugin and the factory that built it.

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
| AI (bring your own key) | The user configures a provider (OpenAI, Anthropic, Google Gemini, or any OpenAI-compatible endpoint) with their own API key. The AI designs an HTML/CSS template; it never writes the text. |

### Configuring AI

Open **Settings > Configure OpenLP > Covers**. Pick a provider, optionally type a model name (the box shows the default), and paste your API key. For a local server such as Ollama choose *OpenAI-compatible server* and enter its address (`https://...`, or `http://localhost:11434/v1`). The key is stored in a private file in your OpenLP data folder, not in OpenLP's settings, so exporting your settings never includes it. The field never shows the key again; it says "saved", and **Clear** followed by **OK** removes it. **Test connection** asks the provider (in the background) whether the key and model work. Default models were checked against each provider's documentation on 2026-10-17 (OpenAI `gpt-6-luna`, Anthropic `claude-haiku-5-5`, Gemini `gemini-3.5-flash-lite`; the OpenAI-compatible default `llama3.1` is an unverified example, change it to a model your server has). When you ask the AI for a design, the cover text and your style hint are sent to the provider you chose; see `docs/security.md`.

### Designing a cover with AI

In the cover editor, type the cover text as usual, optionally describe the style you want (up to 300 characters, for example "warm colours, stained glass"), and click **Design with AI**. The request runs in the background: the button is disabled, the status line says the AI is working, and **Cancel design** stops waiting (the request ends at its next checkpoint and its answer is discarded). When the design arrives, the preview redraws with it, and a note tells you the cover now uses an AI-designed template. The AI only designs the look: your text is always the one you typed. If the AI also drew an icon, it appears as "Uploaded" in the icon list.

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

Work in progress. See the task list in [`odd/tasks/portadas-plugin.md`](odd/tasks/portadas-plugin.md).

## License

GPL-3.0-or-later, same as OpenLP. See [LICENSE](LICENSE).

## References

- [OpenLP source](https://gitlab.com/openlp/openlp)
- [Latent Space: Zach Lloyd on software factories](https://www.latent.space/p/software-factories)
- [Warp Factories announcement](https://fortune.com/press-releases/warp-launches-warp-factories-automate-software-development-2026-08-18/)
- [Cortex: What is an AI software factory?](https://www.cortex.io/post/what-is-an-ai-software-factory)
- [Paulund: Build factories, not features](https://paulund.co.uk/notebook/ai/software-factory-build-factories-not-features)
