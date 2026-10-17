# T15 verification (457eb59) - adversarial, read-only

Gate: `scripts/check.sh` in a detached worktree: ruff clean, **1432 passed, coverage 97.50%**, all checks passed (about 112 s).
A first run, started while my own memory-heavy repro was running, hit the 60 s pytest-timeout in
`test_file_repository.py::test_a_cover_with_a_hostile_deeply_nested_template_does_not_break_the_list`. Alone it takes 0.4 s and the clean rerun
passed, so it is a load flake, but that test is close to a perf budget.
Repro scripts: scratchpad/verify-t15-work/r/ (png2.py, fence2.py, origin.py, sur2.py, perf2.py, repair.py, i18n.py, stored_png.py, ren.py).
No CRITICAL/HIGH/MEDIUM found. All original T15 repros are closed.

## Findings (all LOW or INFO)

1. LOW, CONFIRMED - first-use AI notice is not bound to the destination.
   `lib/editform.py` `on_design` (~l.648) + `lib/ai_settings.py` `DATA_NOTICE_KEY`. The flag is one global boolean in plugin settings.
   Repro (tests/test_zz_notice.py in the worktree): accept for OpenAI, then set provider `openai_compatible` and base URL
   `https://evil.example/v1` -> `asked` stays `['OpenAI']`, the second design request goes out with no prompt. Because the flag is a plain
   setting, an imported `.conf` can also pre-set it to true (OpenLP's import has no section check). The key is protected by SEC-003, so the
   leak is the cover text and style hint only. Fix: store what was accepted (provider id, plus `origin_of(base_url)` for compatible) and re-ask when it differs.
2. LOW, CONFIRMED - repair prompt is unbounded in the number of problems (cost amplification). `application/design_prompt.py:168-176`
   `build_repair_prompt` lists every fatal problem (each cut to 300 chars, but no count cap). Reply with 9000 `<p>text</p>` ->
   second prompt of 803,631 chars (about 200k tokens) sent to the provider. `repair.py`: `[436, 803631]`. The 30,000 cap only covers the previous answer.
   Fix: cap listed problems (e.g. 10) and total characters (e.g. 8,000); `design_cover._Outcome.of` could truncate `problems`.
3. INFO, CONFIRMED - stale status after cancelling by picking a template. `editform.py` `_stop_design_job` (via `_template_picked`) re-enables
   the controls but leaves "Designing with the AI. This can take a minute..." in `status_label` until a preview render replaces it
   (test_pick_template_during_design_v2). Fix: clear or set the status in `_stop_design_job`.
4. INFO, CONFIRMED - decode memory is larger than the comment states. `lib/iconimage.py` `MAX_DECODE_PIXELS` (25M px, "about 100 MB as RGBA"):
   a 16-bit RGBA 5000x5000 PNG made of zeros compresses to a tiny file, is accepted and peaks at 430 MB RSS (0.16 s), on the GUI thread
   (png2.py `25M_px_16bit_zeros`). No crash. Fix: weigh pixels by bit depth (reject or cap 16-bit at about 8M px) or lower the limit.
5. INFO, CONFIRMED - the stored-icon policy checks only the PNG signature. `security/html_policy.py:324-333` `_is_png_data_uri`. A data URI
   with signature + IHDR 2^31 x 2^31, or signature + SVG, is accepted by `sanitize_svg(allow_png_image=True)`, but Qt/libpng refuse both
   safely (stored_png.py: `svg_pixmap` returns null, no file read, no hang). Defense in depth: run `png_size` + dimension cap there too.
6. INFO - `lib/ai_designer.py:60-64`: one message ("entered for another server") for both CHANGED and UNBOUND (legacy key), and a legacy
   stale key also blocks a keyless local server (Ollama) until the user clears it. The settings tab distinguishes the cases; make_designer does not.
7. INFO - `lib/i18n.py` `localize`: the lazy `(.*?)` templates are quadratic on long text (20,000 chars: 0.67 s, 5,000: 0.04 s). Not reachable:
   every caller passes messages of at most about 220 chars (provider text 200, notes 1000, sanitizer messages capped). Keep it that way.
8. INFO - `FileSecretStore.get_api_key` and `get_api_key_origin` are two separate reads, so a key replaced between them could pair a new key with
   the old origin. Needs a concurrent writer inside microseconds; fix by one `get_api_key_with_origin`.
9. INFO - CoverError/ScriptureError messages echo the offending text, so a lone surrogate (typed in a QLineEdit, which keeps it) reaches labels and,
   if logged, a UTF-8 handler. Nothing crashed in the editor for any field (test_zz_sur.py, 7 fields, no exceptions); log handlers swallow encode errors.
10. PLAUSIBLE, not testable on Linux - SEC-004 ADS rule `request_policy._DRIVE` only fires when the path starts with a drive letter. A UNC or
   `\\?\` path with `:stream` is not covered by that line (UNC hosts are blocked elsewhere). Needs a Windows run.

## Claims found sound (tested)

- SEC-001: signature + well-formed IHDR required before Qt; decoder forced to `'PNG'`. Rejected: TIFF/BMP/WebP/ICO/JPG named `.png`; PNG + appended TIFF/SVG/second PNG
  ("extra data after its end"); signature only / signature + IHDR + SVG; bad CRC; truncated; zero dims; 2^31 IHDR; 26M px; 1x25M; Adam7 with short data.
  APNG (acTL + 1000 fcTL/fdAT) accepted but only frame 1 is decoded and the output is re-encoded by Qt, so nothing hostile is stored.
  tEXt 19 MB, iCCP/zTXt bombs, IDAT bomb: all handled by libpng limits, <1 s. FIFO, FIFO via symlink, `/dev/zero` symlink, directory, `/proc/self/mem`:
  rejected instantly. Check is on the open fd (`O_NONBLOCK` + `fstat`), so there is no check/open race. SVG upload uses the same reader.
- SEC-002: 40k-80k spaces after a fence: 5 ms. Also fast (<0.35 s): 40k fences, `` ` ``*512k, CRLF fences x20k, 200k `[`, 100k nested `{"a":`, 500k-digit number,
  ```` four-backtick fences. Cap exactly at 512*1024 chars (cap+1 refused). `RecursionError` is caught.
- SEC-003: `origin_of` + `validate_base_url`: userinfo (`https://good@evil`, `good.com\@evil.com`, `evil.com\@good.com`), query, fragment, whitespace, control chars, bad
  ports (`:99999`, Arabic-Indic digits, `+80`), `http` to non-local all refused. Case, default port (`:443`, `:0443`, empty `:`) collapse to the same origin as the same destination
  (urllib3 agrees); trailing dot, IDN vs punycode, full-width and `%2e` forms give a different string (fail closed). I diffed `origin_of` against what `requests`/urllib3 actually
  connect to for 40 URLs: no URL yields the victim's origin string while connecting elsewhere. http->https is a different origin. Redirects are never followed (`allow_redirects=False`).
  Only two readers of the key exist: `make_designer` and the settings tab's Test connection; both check `key_server_status` against the same text they use for the request, and the
  fixed-address providers never take a URL. Original import repro (key_exfil_settings_import.py) now stops in `make_designer`. Legacy keys without origin are refused.
  `set_api_key` after the URL is saved, so the origin is the new URL.
- SEC-004: forcing `is_url_allowed` to raise blocks the request, with no excepthook output (interceptor_failopen.py); policy now catches OSError/ValueError/UnicodeError itself.
- SEC-005: 30 new shapes at about 190 KB all finish in under 0.6 s (nested @media/@supports/parens 20k deep, unclosed `{`/`(`, 12k distinct bad props/selectors/urls, `@import` spam,
  font-face/keyframes spam, nested skipped tags, mismatched end tags, 60k unclosed `<p>`, 8k SVG paths, 40k-segment path). >100 distinct CSS problems drops the sheet.
  `_strip_delimiters` is one pass and cannot rebuild a delimiter.
- SEC-006: lone surrogates rejected in label/titles/subtitle/readings label, key verse and readings (message echoes them, see 9), custom template (text, attr, comment, tag name, CSS
  string/selector/comment, style attr, lang, title, doctype), SVG (attr, text, id), cover JSON (`label`, ids). Entities (`&#xD800;`) become U+FFFD. JSON `\ud800` in reply
  keys is harmless; in `html` it is rejected by the sanitizer; in `notes` and the style hint it passes but only reaches a QLabel (plain text) and `json=` (ensure_ascii),
  so no UnicodeEncodeError. Editor never stays busy. Gemini model name with a surrogate is refused by the adapter.
- SEC-007: plugin loaded as `contrib.plugins.renamed` redacts keys on the child logger `...renamed.adapters.ai.http`, with traceback (ren.py). A different package name is not covered (expected).
- T13b fixes: factory exception shows a fixed message; notes and provider text are PlainText (textFormat 0); template pick or re-click cancels the job and drops the design; the icon
  from before the design is restored by "use template" and after a template pick; cancel-then-redesign delivers only the new result; busy-state, close-during-design OK (37 tests incl. mine).
- 24f4701: message boxes are PlainText; tooltips escaped; `has_search=False`; all label sinks that show untrusted text are PlainText (checked every QLabel/setToolTip in lib/); the notice
  default is a real modal PlainText box; a bool flag in settings reads back correctly for 'false', '0', 'abc' (all False).
- dadb0d4 i18n: no `{name}` placeholder mismatch between any English key and Spanish value, every `%N` is within the English field count and complete; substitution is a single `re.sub`
  pass, so a value containing `%1` or `%2` is never re-expanded; values are localized separately (depth-limited), and `.format` is applied to translated templates, not to user values.
  The translator returns `None` for unknown text. Only the About string holds HTML and it is fixed.
