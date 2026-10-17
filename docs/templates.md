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
`href`/`url()` and unsafe CSS are removed and reported (non-fatal). Hard-coded visible text (including anything CSS could
draw, see below), missing required placeholders, oversized or too deeply nested input are fatal. Limits: 200 KB,
24 nesting levels, 5000 elements. Threat model and reasoning: `docs/security.md`.

## CSS allowlist (for template and AI authors)

CSS in `<style>` blocks and `style="..."` attributes is tokenized (CSS Syntax Level 3), validated token by token and
written back in canonical form (`portadas/security/css_policy.py`). Comments disappear; an invalid declaration or rule
is dropped and reported while the rest survives; unreadable CSS (unterminated string or comment, bad `url()`, unbalanced
brackets, `<`, `&`, `{{`) drops the whole block.

| Part | Allowed | Everything else |
|------|---------|-----------------|
| At-rules | `@font-face`, `@media` (conditions use only words, numbers and `( ) : , / = >`; at most 2 levels) | `@import`, `@keyframes`, `@supports`, `@page`, `@namespace`, `@charset`, ... dropped |
| `@font-face` | `font-family` (one name from the font list below), `font-style`, `font-weight`, `font-stretch`, `font-display`, `src: url(../../assets/fonts/<file>.ttf\|otf\|woff\|woff2) [format("truetype"\|"opentype"\|"woff"\|"woff2")]`, comma separated | `local()`, remote or non-font urls, `unicode-range`, other descriptors dropped |
| Selectors | type, `.class`, `#id`, `*`, `[attr]`, `[attr=value]` (+ `^= $= \|=`), `> + ~` and descendant, pseudo-classes, `::before`/`::after`/`::marker`..., `:not() :is() :where() :nth-*()` | strings, urls, `:lang()`, `:has()`, at-keywords: the rule is dropped |
| Properties | layout and box model, flex/grid, sizing, position, typography (`font-size`, `font-weight`, `font-style`, `font-variant*`, `line-height`, `letter-spacing`, ...), colour, `background*`, `border*`, `outline*`, `box-shadow`, `text-shadow`, `transform*`, `filter`, `backdrop-filter`, `opacity`, `clip-path`, `mask*`, SVG paint properties (`fill`, `stroke*`, `stop-*`...), a few `-webkit-` text properties, and custom properties `--x` | `font` shorthand, `animation*`, `transition*`, `cursor`, `text-overflow`, `font-feature-settings` and any unlisted property |
| Functions | `rgb rgba hsl hsla`, `linear-gradient radial-gradient conic-gradient` (+ `repeating-`), `calc min max clamp var`, transforms (`translate* scale* rotate* skew* matrix*`), filters (`blur brightness contrast drop-shadow grayscale hue-rotate invert opacity saturate sepia`), grid (`repeat minmax fit-content`) | `attr() counter() image-set() element() src() local() env() expression()` ... |
| `url()` | `#fragment` or `../../assets/{fonts,backgrounds}/<file>` | everything else |
| Strings | only font names in `font-family`, `format("...")` in `@font-face src`, and the empty `content: ""` | any other string token (also in custom properties, selectors, media conditions) |
| Fonts | bundled `Outfit` and `Playfair Display`; `Arial, Helvetica, "Helvetica Neue", Georgia, "Times New Roman", Times, Verdana, Tahoma, "Trebuchet MS", "Courier New", Courier, "Segoe UI", Roboto, "Open Sans", "DejaVu Sans/Serif", "Liberation Sans/Serif", "Noto Sans/Serif"`; generic `serif sans-serif monospace cursive fantasy system-ui ui-*` | symbol fonts (Wingdings, Webdings, ...) and any other name |

Text-bearing properties are **fatal** (`css-content-text`) when they could draw text that is not a user value:

- `content` may only be `""`, `none` or `normal`;
- `quotes` and `list-style`, `list-style-type`, `list-style-image` may only be `none`;
- `counter-reset`, `counter-increment`, `counter-set` are refused;
- `var()` is refused in these properties and in `font-family`, so a custom property cannot smuggle a value into them.

**Lists:** `<ol>` is not allowed (it is removed with its content) and `* { list-style: none }` is emitted ahead of every
template, so neither `<ul>`, a bare `<li>` nor `display: list-item` draws a bullet or number. Write
`list-style: none` on your own lists if you like; nothing else is accepted.

Practical advice for AI prompts (T12): write plain, static CSS with the properties above; use `{{placeholders}}` only in
element text; put decoration in `::before`/`::after` with `content: ""` and a background, or in inline SVG; do not use
`@import`, animations, `font:`, `list-style`, `local()` fonts or any text in CSS.
