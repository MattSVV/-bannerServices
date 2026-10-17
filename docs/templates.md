# Cover templates

A template lives in `portadas/templates/<id>/` as `template.html` + `manifest.json` (id, name, description,
`required`/`optional` placeholders, canvas 1920x1080). The engine is `portadas/domain/templating.py`: plain
`{{name}}` substitution in a single pass, no expressions, no code execution (Mako is never used for templates).

| Placeholder | Content |
|-------------|---------|
| `{{label}}`, `{{title_main}}`, `{{title_accent}}`, `{{subtitle}}`, `{{key_verse}}`, `{{readings_label}}` | user text, `html.escape(quote=True)`; subtitle line breaks become `<br>` |
| `{{readings}}` | one `<li>` per reading, built by our code (put it inside a `<ul>`) |
| `{{icon}}` | an already sanitised SVG string, inserted verbatim |
| `{{empty_fields}}` | hook classes for every empty field, for example `no-subtitle no-readings` |

Rules: user text containing `{{...}}` is never expanded; unknown or malformed placeholders are errors; a required
placeholder must appear in the template and have a non-empty value.

## CSS hook convention

Put `class="{{empty_fields}}"` on `<body>` and hide optional blocks with `body.no-<field> .block { display: none; }`.
The hook is `no-` plus the placeholder name with `_` turned into `-` (`no-title-accent`, `no-key-verse`,
`no-readings-label`). Placing a placeholder directly inside its element (no whitespace) also lets `:empty` work.

## Overflow detection

The renderer reports which fields do not fit by looking for elements whose CSS class is the placeholder name with `_`
turned into `-` (`title-main`, `title-accent`, `subtitle`, `key-verse`, `label`, `readings-label`, `readings`). Give
each field's element that class, as the built-in templates do.

## Assets

Fonts are bundled (SIL OFL, licenses next to them) in `portadas/assets/fonts/` and referenced from a template as
`url(../../assets/fonts/<file>)`. Icons are hand-made SVGs in `portadas/assets/icons/<slug>.svg` (viewBox 64x64,
`currentColor`). Templates must have no JavaScript and no remote resources; the sanitizer in
`portadas/security/html_policy.py` enforces this for untrusted templates, and the built-ins must pass it unchanged.

## Sanitizing untrusted (AI) templates

`portadas/security/html_policy.py`:

- `sanitize_template(html, required=('title_main',)) -> SanitizeResult(html, violations)`; `result.accepted` is false
  and `result.html` is `None` when a fatal violation exists.
- `require_safe_template(html, required)` returns the sanitized HTML or raises `TemplateRejected` (has `.violations`).
- `sanitize_svg(svg) -> SanitizeResult` for an inline SVG icon (one `<svg>` root, no text, no styles).

The output is rebuilt from an allowlist as a canonical document. Disallowed elements, `on*` attributes, remote
`href`/`url()` and bad `<style>` blocks are removed and reported (non-fatal). Hard-coded visible text (including CSS
`content` text), missing required placeholders, oversized or too deeply nested input are fatal. Limits: 200 KB,
24 nesting levels, 5000 elements. `url()` may only be `#fragment` or `../../assets/{fonts,backgrounds}/<file>`.
