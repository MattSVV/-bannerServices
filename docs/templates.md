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

## Assets

Fonts are bundled (SIL OFL, licenses next to them) in `portadas/assets/fonts/` and referenced from a template as
`url(../../assets/fonts/<file>)`. Icons are hand-made SVGs in `portadas/assets/icons/<slug>.svg` (viewBox 64x64,
`currentColor`). Templates must have no JavaScript and no remote resources; the sanitizer in
`portadas/security/html_policy.py` enforces this for untrusted templates, and the built-ins must pass it unchanged.
