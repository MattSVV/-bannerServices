# T15 security review (efa6e78) - delegated read-only sdd-security reviewer

Verdict: **CLEAR for CRITICAL/HIGH**. 0 CRITICAL, 0 HIGH, 3 MEDIUM, 4 LOW, plus INFO items. Repro scripts were kept outside
the repo (scratchpad `t15/`); the fixes below carry their own regression tests.

## Threat model (short form)

Assets: A1 provider API keys; A2 exact cover text and render uptime; A3 local files and the network; A4 library and
service files; A5 privacy (cover text sent to a provider); A6 the OpenLP process.
Actors: hostile provider or endpoint; attacker-controlled files (icon uploads, imported `.conf`, `.osz`); writers of the
data folder; other local users; LAN web remote; supply chain.

## Findings

| ID | Sev | Where | Finding | Task |
|----|-----|-------|---------|------|
| SEC-001 | MEDIUM | `lib/iconimage.py:33-71` (`prepare_png_icon`, `_announced_size`), `lib/editform.py:562-575` | The icon upload accepts a PNG by suffix only. A TIFF named `.png` segfaults (QBuffer destroyed before QImageReader: use-after-free); an SVG named `.png` renders local files outside the allowed roots; a FIFO `href` hangs; the file picker also blocks on a FIFO. | T15a |
| SEC-002 | MEDIUM | `application/design_parse.py:28` (`_FENCE`) | ReDoS: three backticks plus 40k spaces takes about 9 s and holds the GIL. | T15a |
| SEC-003 | MEDIUM | secret store, `ai_config`, settings tab | The `openai_compatible` key is bound to the provider, not to the endpoint. OpenLP's settings import writes any key (upstream `mainwindow.py:923-949` section check is a no-op), so an imported `.conf` that changes `portadas/ai base url` sends the stored key to the attacker. | T15a |
| SEC-004 | LOW | `adapters/qt_renderer.py:167-171` | The request interceptor fails open on an exception. `is_url_allowed` is not total (OSError, ValueError, UnicodeError); Windows drive-colon handling. | T15b |
| SEC-005 | LOW | `css_policy.py:662-663`, `html_policy.py:203-207`, `design_prompt.py:185-191` | Quadratic CPU: list membership for problems, skip stack, `_strip_delimiters` loop; `MAX_PREVIOUS_CHARS` too high. | T15b |
| SEC-006 | LOW | `domain/cover.py` `_reject_invisible`, `html_policy._prepare` | Lone surrogates (category Cs) are accepted and later raise UnicodeError; editor `_busy` not reset on failure. | T15b |
| SEC-007 | LOW | log redaction install | Redaction is bound to the hard-coded logger name `contrib.plugins.portadas`. | T15b |
| INFO | INFO | message boxes, list tooltips, media item `has_search`, first AI send, docs | Rich-text rendering of user/AI text; `has_search=True` without `search()` (web API 500); no first-use notice before data leaves the machine; docs gaps (see T15c). | T15c |

Also carried in from the T12c verification (`t12c-verify.md`): `api-keys.corrupt` being a directory makes every save fail
with no path in the message; the watcher reason can mask a real HTTP error that lands just after the deadline (T15b).

Upstream (OpenLP) issues to **report upstream, not filed**: settings import section check is a no-op; `.osz` member names
with path components; web remote authentication off by default.
