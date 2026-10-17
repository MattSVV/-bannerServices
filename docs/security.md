# Security

## Sanitizer threat model

Templates (and inline icons) written by an AI are **untrusted input**. They are rendered by QtWebEngine inside a
sandbox (`portadas/adapters/qt_renderer.py`: no page JavaScript, request interceptor, one navigation, off-the-record
profile) and, before that, rebuilt by the sanitizer (`portadas/security/html_policy.py` and `css_policy.py`). The
sanitizer and the sandbox are two independent layers; a bypass of one must not be enough.

Goals, in order of importance:

1. **No script execution.** No `<script>`, event handlers, `javascript:` URLs, `<foreignObject>`, `<iframe>`, `<object>`,
   SVG animation or any other element outside the allowlist.
2. **No network or file access** beyond the plugin's own `assets` and `templates` folders: `url()` and `href` can only be
   a `#fragment` or `../../assets/{fonts,backgrounds}/<file>`; no `@import`, `image-set()`, `src()`, `local()`.
3. **The only visible text is the user's placeholder values.** A cover is shown to a congregation: the AI must not be
   able to add words, numbers, bullets or symbols. This covers text nodes, SVG `<text>`, CSS `content`, list markers and
   numbering, `quotes`, counters, `attr()` and strings smuggled through custom properties.
4. **No re-expansion of user text.** Substitution is a single pass (`domain/templating.py`); `{{...}}` inside user text,
   attributes, CSS or icons is never expanded or accepted.
5. **Bounded cost.** Input is limited to 200 KB, 24 nesting levels and 5000 elements; the CSS tokenizer is linear and
   limits bracket nesting; scripture references are capped at 200 characters and parsed in linear time.

### How it is enforced

- **HTML**: parsed with the standard library, rebuilt from an allowlist (never patched in place), so the output does not
  depend on how a browser would have parsed the input. Every non-blank text node must be exactly one placeholder.
- **CSS**: never inspected with regular expressions on a "normalised" copy (that approach was bypassed in T06b with
  comment markers inside strings, escaped `\/*` and escaped quotes). Instead:
  1. a tokenizer implementing CSS Syntax Module Level 3 reads the text the way Chromium does;
  2. the tokens are validated against allowlists (at-rules, selectors, properties, functions, `url()` targets, strings);
  3. the result is **re-serialized from the validated tokens**, tokenized again and compared with what was validated, so
     what was checked is exactly what the browser will read, and sanitizing the output again changes nothing.
  The allowlist is documented for authors in `docs/templates.md`.
- **Strings** are the main way to inject text in CSS, so a string token survives only as a `font-family` name from a fixed
  list, as `format("...")` in `@font-face`, or as the empty `content: ""`.
- **Lists** would add markers or numbers: `<ol>` is removed and `* { list-style: none }` is forced first; `list-style*`
  and `quotes` accept only `none`.
- **Icons** (`sanitize_svg`): one `<svg>` root, SVG elements only, no text at all (not even a placeholder-looking one),
  `style` attributes go through the same CSS policy.
- **Uploaded icons** (the editor's Upload button). These are the *user's own* files, never AI output, and they pass
  `application/icon_upload.py` first. An SVG with active content (script, event handler, `foreignObject`, animation,
  link), text or an embedded image is **rejected**, not silently cleaned; a clean one is stored as the sanitizer's
  rebuilt markup. A PNG is scaled down by the UI (at most 256 px, 96 KB), then wrapped in an SVG `<image>` with a
  `data:image/png;base64,` URI. Only `sanitize_svg(..., allow_png_image=True)` accepts that `<image>`: strict base64,
  at most 96 KB decoded, PNG signature, any other `href` dropped. `sanitize_template` has no such option, so AI
  templates can never carry an `<image>`. The stored icon is sanitised again with the option on every render.

## API keys

Bring-your-own-key means the plugin holds a credential for each AI provider the user configures. The design goals are
that the key never appears in OpenLP's settings or their export, in logs, in the UI, or in a file other users can read.

### How the key is stored (`portadas/adapters/secret_store.py`)

- **Where.** `<OpenLP data>/portadas/secrets/api-keys`, a small JSON file `{"version": 1, "keys": {provider: key}}`.
  Non-secret settings (provider, model, server address, timeout) stay in OpenLP `Settings` under `portadas/ai ...`.
  Nothing secret is ever put in `Settings`, so *Export settings* and backups of `OpenLP.conf` do not contain keys.
- **POSIX (Linux, macOS).** The directory is `0700` and the file `0600`. The file is written atomically: a private temp
  file (`mkstemp`, mode `0600`, never readable by others even briefly) is flushed with `fsync` and renamed over the old
  one, so a crash or a full disk leaves the previous content intact. When reading, the file is **refused** (a warning
  without the key is logged and the key reads as absent) if it is a symlink, not a regular file, owned by another user,
  or readable or writable by group or world. Changing a key over such a file moves it aside to `api-keys.corrupt`
  (owner-only, so the other providers' keys are not lost) and starts a private one; its content is never merged.
- **Concurrent changes.** Every change is a read-modify-write under a process lock and, on POSIX, an `flock` on
  `<secrets>/.lock` (bounded wait of 5 s), so two writers cannot drop each other's key. A file that is trusted but
  cannot be parsed or decrypted is moved to `api-keys.corrupt` (one backup) before a new file is started, never
  overwritten without a trace. By design, a second incident replaces the earlier backup (only the latest is kept), and
  under extreme contention (dozens of processes writing at once) the 5 s wait can run out; the writer then gets "being
  changed by another OpenLP window" and nothing is lost or half written. A symlinked secrets *directory* is refused: `chmod` would follow it.
- **Key shape.** The store accepts exactly what the adapters accept (`KEY_PATTERN` in `application/ai_config.py`:
  printable ASCII without spaces, 6-500 characters), so a saved key is always a usable one.
- **Windows.** The file content is encrypted with DPAPI (`CryptProtectData`, bound to the signed-in Windows user, no UI
  prompt) via `ctypes`, so it is useless if copied to another account or machine. The DPAPI code path is unit-tested on
  every platform with a mocked crypt API.
- **Keyring.** The OS keyring is not used: it needs a dependency OpenLP does not ship (see the dependency budget).
- **UI.** The key field is a password field. A stored key is never shown again: the field stays empty and says
  "saved". Removing it takes **Clear** and then **OK** (Cancel keeps it). A key typed for one provider is dropped when
  the user switches provider, so it can never be saved under the wrong one.
- **Server address.** For OpenAI-compatible servers only `https://` is accepted, plus `http://` to `localhost`,
  `127.0.0.1` or `::1`. User names and passwords in the URL, queries and fragments are refused, because URLs end up in
  logs and error messages.
- **Key bound to its server (SEC-003).** The key of an OpenAI-compatible server is stored together with the normalized
  origin it was entered for (`scheme://host[:port]`, in the secrets file as `origins`). It is sent only while the
  configured address has that same origin; otherwise the editor and *Test connection* refuse and ask for the key again,
  and the settings tab shows the host the key goes to. This closes the route where an imported `OpenLP.conf` changes
  `portadas/ai base url` and the stored key follows it to the attacker. **Migration:** a key saved by an earlier build
  has no origin and is treated as unverified: it is not sent until the user types it again (once) in the settings tab.

### Log redaction (`portadas/security/redaction.py`)

A filter is installed on the `contrib.plugins.portadas` logger hierarchy when the plugin loads. Every record is rewritten
(message, arguments, traceback) so that the exact keys the secret store has handled in this process, and anything shaped
like an OpenAI/Anthropic/Gemini key, a bearer token or an `x-api-key` header, becomes `[redacted]` before any handler
(OpenLP's log file, the console) sees it. Error messages from the connection test go through the same function.
Code must still never log a key on purpose; the filter is the safety net for accidents such as an exception message or a
request URL (Gemini accepts `?key=`).

### Threat model for keys

| Threat | Mitigation | Residual |
|--------|------------|----------|
| Another local user reads the key | `0700`/`0600`, refused if loose, DPAPI on Windows | root/administrator can read it |
| Key leaks through a settings export, a support upload or a backup of `OpenLP.conf` | Keys are not in `Settings` | A backup of the whole data folder includes the secrets file; treat it like `~/.ssh` |
| Key leaks into `openlp.log` | Redaction filter, no deliberate logging | A key of an unknown shape that was never stored here cannot be recognised |
| Symlink or file swapped by another user | `lstat` checks, ownership check, atomic rename | A time-of-check race by the same user is not defended |
| Malware running as the same user | None: any program that can run the plugin can read what the plugin can read | Accepted. Use provider-side spending limits and revoke leaked keys |
| Shoulder surfing | Password echo mode, key never shown again | A key can be seen while being typed if the user reveals it with the OS |

### AI provider calls (`portadas/adapters/ai/`, T12)

What leaves the machine: the **cover text** (label, titles, subtitle, key verse, readings), the **style hint** the user
types, and our fixed design rules. Both texts go to the provider the user chose (OpenAI, Anthropic, Google, or the
OpenAI-compatible server at the address they set), under that provider's data policy. Nothing else is sent: no other
covers, no files, no OpenLP data. Without a key nothing is ever sent. The text and the hint are placed in marked blocks
and the model is told they are data, not instructions (`application/design_prompt.py`); stripping control characters
and the block delimiters makes it hard to break out, but a prompt cannot be a security boundary, so the real boundary is
the sanitizer: whatever the model answers is untrusted and passes `sanitize_template` / `sanitize_svg` (never the
uploaded-PNG option) before it is stored or rendered, and again on every load and render.

| Rule | How |
|------|-----|
| The key never appears in a URL | Gemini uses the `x-goog-api-key` header; OpenAI/compatible use `Authorization`, Anthropic `x-api-key` |
| No key in errors or logs | Adapters build error messages from fixed text plus a shortened, redacted provider message; exception text from `requests` (which can carry URLs or headers) is never used; `register_secret` makes the exact key redactable |
| No proxy, no `.netrc` | The session has `trust_env = False`: `HTTP(S)_PROXY` would send the bearer key in clear text to the proxy and `.netrc` could replace the `Authorization` header. A proxy, if ever needed, must be an explicit setting |
| No redirects | `allow_redirects=False`: a custom auth header would otherwise travel to the redirect target |
| Bounded | `AiConfig.bounded_timeout` (5-300 s) per wait on the socket, **and a wall-clock budget of twice that timeout for the whole call** (every attempt, backoff and the streaming of the body; a watcher thread per attempt shuts the attempt's sockets down at the deadline or on cancellation, so a server that trickles the headers or the body one byte at a time is cut off even while `requests` is blocked on a read. DNS resolution and the connect phase are not covered by the budget, only by the per-wait timeout). At most 2 retries on 429/5xx (1 s, 2 s backoff or `Retry-After`, capped at 10 s and interrupted by cancellation; a pause that would use up the budget fails at once), responses refused beyond 2 MB while reading |
| One repair round | A rejected answer is sent back once with the violations; a second rejection is an error, never a loop |
| Plain `http://` | Only to `localhost`/`127.0.0.1` (OpenAI-compatible), enforced by `validate_base_url` |
| Off the GUI thread | `lib/background.py` runs the blocking call on a `QThreadPool` and delivers the result on the GUI thread; a closed dialog cancels the job: the request stops at its next checkpoint (between chunks and attempts, `application/cancellation.py`); a wait on the socket ends by its own timeout |

The editor's AI mode (`lib/editform.py`, T13) adds no new capability: `lib/ai_designer.make_designer` reads the saved
settings and the key on the GUI thread (a bad server address or an unreadable key file becomes a fixed message), the
request runs through `lib/background.py`, and only the sanitised template and icon of `DesignedCover.apply_to` reach the
form; the visible text always comes from the form fields. Every message shown (adapter, use case or unexpected error)
passes `redact` again, and an unexpected exception is shown by type name only. The dialog allows one design at a time,
disables *Save* while it runs, and a closed dialog cancels the job and ignores a late callback.

An AI template is stored with the cover as `custom_template_html` in its JSON (additive key, schema 1). It is
re-sanitised when the file is read (a stored template that no longer passes is dropped and the cover still loads,
falling back to its `template_id`) and again in `CreateCoverFromTemplate.compose`. There is no path involved, so there is
no traversal surface: relative URLs resolve from the built-in folder named by `template_id` (`base_dir`), which is the
same allowlisted root the renderer's request filter already enforces.

### Residual risks (accepted)

- Logging blind spots. Redaction covers the `contrib.plugins.portadas` logger hierarchy. `http.client` debug output
  (`http.client.HTTPConnection.debuglevel`) is printed to stdout, not logged, and a handler attached to a child logger
  of `urllib3` or `requests` by other code sees records before this filter. Do not enable those in a build that holds a
  real key.
- The model can ignore the style hint or produce an ugly design that passes every check. The preview is the check.
- A provider can bill for a request whose answer we then reject. The single repair round caps this at two calls per
  design; use provider-side spending limits.

- Rendering cost within the limits (many nested filters, patterns or `<use>` references) can slow a render; the renderer
  has a timeout, and the user sees the failure instead of a hang.
- The render timeout is soft. Page layout and `QWidget.grab()` run synchronously on the GUI thread, and a timer cannot
  interrupt them, so a pathological page can freeze the UI for longer than the timeout. The bound is therefore on the
  work, not only on the clock: the canvas is capped at 3840x2160 pixels, the HTML at 2 MB, the sanitizer limits the CSS
  and SVG complexity, and the renderer re-checks the deadline after every grab and fails the render if it was exceeded
  (so a late image is never returned as a success). A page that blocks inside Chromium for a long time is still not
  killed; only a separate render process would give a hard limit.
- Saving a cover moves two files (PNG, then JSON, which is the commit marker). A crash between the two moves leaves the
  previous cover with its newer image, or an invisible orphan PNG for a new cover; neither loses data. Error messages
  shown to the user never contain file system paths; the details go to the log.
- A template can still look wrong or be unreadable (colours, sizes, overlapping boxes); the overflow report and the
  preview exist for that. The sanitizer guarantees what it can show, not that it looks good.
- The tokenizer follows the CSS Syntax specification, not a specific Chromium build, so "what is checked is what the
  browser reads" holds for the known attacks, not as a proof. T06c closed the two known disagreements: unicode-range
  tokens (`U+41url(...)`) are now one token and are refused everywhere (the `unicode-range` descriptor is dropped too),
  and plain SVG attribute values reject a bare `(` or `:`. `-webkit-line-clamp` is off the allowlist because the browser
  draws a hard-coded ellipsis. The rendered tests (`tests/test_sanitizer_rendered.py`) are the check that both agree.
- `hyphens: auto` and `word-break` change how user text breaks into lines but add no text. They are accepted.

### Tests

- `tests/test_css_policy.py`: tokenizer cases, allowlists, idempotence and "no string outside the allowed contexts" over
  generated hostile input.
- `tests/test_sanitizer_bypasses.py`: every confirmed T06 finding as a regression (rejected, or neutralised with the
  reported violation).
- `tests/test_sanitizer_rendered.py`: real QtWebEngine, pixel based. Pages whose only placeholder is hidden must be flat
  background after sanitizing; the same pages, unsanitized, must draw something (control, so the harness is known to see
  the attack); the built-in templates must look identical before and after sanitizing.
