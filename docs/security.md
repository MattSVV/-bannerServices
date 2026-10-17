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

### Residual risks (accepted)

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
