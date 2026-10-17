# Verification of 8fe4dc5 (T20) and ed06c00 (T12b)

Repro scripts: /tmp/claude-1000/-home-mvelasco-Proyectos-Personales-bannerServices/2ebc9bc9-11b3-4834-8e77-14c91b80a1aa/scratchpad/verify-t20-work/ (trickle.py, deep.py, store.py, delim.py).

## Findings

1. MEDIUM, CONFIRMED. Wall-clock budget is bypassed by a trickling body with Content-Length, and by trickled response headers.
   - Repro: `trickle.py <data> body` and `... headers` (timeout=3, so budget 6 s). Both were still running when `timeout 40` killed them (exit 124). The chunked variant is correctly stopped at 6.0 s.
   - Cause (http.py `_read`, line ~182): `iter_content(8192)` blocks in `read(8192)` until 8192 bytes arrive; each recv is under the per-read timeout, so 1 byte per 0.5 s needs ~68 min per chunk, and `_remaining()` is only reached between chunks. The header phase (`session.request` returning) has no wall-clock bound either (stopped only by http.client's 100-header cap, ~50 s here).
   - Fix: arm a `threading.Timer(deadline)` per attempt (also covering `session.request`) that closes the connection (`response.raw` / `response.close()`, or the socket shutdown), or read with `response.raw.read1`/small chunks and cancel via the timer. Add tests for the Content-Length and header trickle with a real local socket server (current tests probably only cover chunked or fake sessions).
   - Related, PLAUSIBLE low: `self.sleep(delay)` for backoff (<= 10 s) is not cancellable; DNS resolution and multi-address connect (urllib3 applies the connect timeout per address) are outside the budget.
2. LOW, CONFIRMED. `FileSecretStore.set_api_key/delete_api_key` on an untrusted-but-valid file (for example chmod 644) silently drops all other providers' keys and leaves no backup.
   - Repro: store.py ("after chmod644 read ... after set on 644 file": the gemini key was lost, no `.corrupt` file).
   - Location: `_read_for_update`, secret_store.py ~line 186 (`return self._read()` for a trust problem).
   - Fix: move the untrusted file to the backup too, or refuse with SecretStoreError.
3. LOW, CONFIRMED. Under heavy contention (16 processes x 64 writes) 44 of 64 writes failed with "being changed by another OpenLP window" because the 5 s non-blocking poll is unfair. No lost update (all 4 providers kept). Unrealistic load, so info only; a blocking `flock` in a helper thread or a longer wait would fix it.
4. LOW, CONFIRMED (by design). A second corruption overwrites the earlier `api-keys.corrupt`, so the first backup is lost (docs say "the latest"). Optional fix: timestamped backup.
5. LOW, PLAUSIBLE. `_prepare_directory()` is called in `_exclusive` before the `try`, so an `os.chmod` OSError (directory owned by another user) escapes as a raw OSError instead of SecretStoreError (secret_store.py ~line 123 and ~line 283).
6. LOW, CONFIRMED. T20 guard names the victim, not the culprit: a leaked `QTimer.singleShot(..., quit)` from test_a fired in test_b and the guard reported test_b. The abort is correct, but the message should say "or an earlier test". Same blind spot: the guard only runs for tests that request `qapp`.
7. INFO. When `render()` is interrupted from outside, the job is not aborted; it lives until its own deadline (qt_renderer.py ~line 411). Harmless; consider `job.abort()`.
8. INFO. The remaining bare `QTimer.singleShot` in tests (test_qt_renderer.py lines 353, 426) cannot be cancelled if the test fails before it fires. They only quit/close local objects, so they are safe.

## Checked and found sound

- T20: full suite run 3 times, 1270 passed each (123 s, 130 s, 143 s), no hang. Slowest renderer tests 1.5 s, well under the 60 s per-test limit.
- T20: the conftest guard fires: a test that leaves a quit pending makes the run stop (Exit, naming the test). `event_loops_alive` has no false positive in 3 clean runs (40 ms timer, 20 ms threshold).
- T20: no other `QCoreApplication.exit/quit` in tests or code (rg). Watchdog now closes the renderer and stops its timers at teardown. `'result' not in outcome` raises RenderError; check.sh wraps pytest in `timeout --kill-after`.
- T12b depth: `MAX_DEPTH` is enforced before any recursion. 24 levels pass, 25 are `too-deep`, for HTML (div, span-in-p, unclosed) and SVG (23/24 g), up to 5000 levels, with no RecursionError. Nested CSS (braces, parens, calc, @media, brackets, in `<style>` and in a style attribute) are rejected without exceptions. `list()` now catches any Exception per entry. Every `json.loads` site handles RecursionError or the same errors.
- T12b proxy: the only `requests.Session` in the code base is `_new_session()` with `trust_env=False`; there is no `requests.get` or urllib use elsewhere.
- T12b delimiters: `<<<<<<>>>`, `<<>>><`, `<<<>>><<<`, 15000-char alternating nests, and invisible characters between brackets all end with no `<<<`/`>>>` left. Cost is quadratic (5000 levels = 1.1 s), acceptable because fields are bounded. Entity or fullwidth lookalikes are not delimiters for the parser, and are only a model-level concern.
- T12b store: no lost updates across 16 processes; a corrupt file is moved to `api-keys.corrupt`; a symlinked directory is refused; a symlinked file is replaced, not followed; KEY_PATTERN rejects short, spaced, non-ASCII and over-500 keys.
- T12b chunked-body trickle is cut at exactly 2x timeout (6.0 s).
