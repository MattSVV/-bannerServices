# T12b: confirmed AI-adapter findings (independent verifier of 9a21107 and 8c0b962)

Repro scripts are in `/tmp/claude-1000/-home-mvelasco-Proyectos-Personales-bannerServices/2ebc9bc9-11b3-4834-8e77-14c91b80a1aa/scratchpad/verify-t12/` (`t_http`, `t_san3`, `t_tamper`, `t_proxy`, `t_store`, `t_design` and others).

1. **Medium. No total deadline on provider responses.**
   - Location: `portadas/adapters/ai/http.py:137-138`. `requests` applies `(connect, read)` per socket read, so a server trickling 1 byte/s kept the call alive for 60 s at `timeout=5`, and retries multiply that.
   - Fix: enforce a wall-clock deadline while streaming (check elapsed time per chunk), cover the whole retry loop with it, and give `BackgroundJob.cancel()` a way to abort, e.g. a cancel flag checked per chunk.
2. **Medium. A deeply nested template raises an uncaught `RecursionError`.**
   - Location: `html_policy.py:337` (`_check_text` recursion).
   - Repro: `<div>`×5000 in sanitize_template, in a tampered `custom_template_html`, or in a provider reply. `FileCoverRepository.list()` (`file_repository.py:204`) then fails entirely, hiding every cover. It also escapes `DesignCoverWithAI.design` and `compose`.
   - Fix: make the depth limit enforced before any recursion (iterative walk or early depth abort in the parser), convert to a fatal violation, and make `list()` robust to any per-entry exception.
3. **Medium. Proxy environment variables and `.netrc` are honored.**
   - Cause: a default `requests.Session()` has `trust_env=True`.
   - Effect: `HTTP_PROXY` sends the bearer key in cleartext to the proxy, and `.netrc` replaces the Authorization header.
   - Fix: set `session.trust_env=False`. Proxy support, if wanted later, becomes an explicit setting; document it.
4. **Low. Lost updates in `FileSecretStore.set_api_key`.**
   - Cause: read-modify-write without a lock (4 threads → 1 key kept).
   - Fix: add a process lock, plus a file lock if cheap. Also: a corrupt or undecryptable file must NOT be silently overwritten (keep a backup or refuse with an error), and do not chmod the target of a symlinked secrets dir (refuse a symlinked dir).
5. **Low. Prompt delimiter stripping is single-pass.**
   - Location: `design_prompt.py:47` and `:182`. User text can rebuild `<<<`/`>>>`.
   - Fix: strip until stable, or encode the user data (e.g. as a JSON string) instead of delimiters.

Plausible issues, fix if cheap:
- Repair round: if the first answer had a good template and only the icon was bad, keep that template when the repair template is worse.
- Make the store's key validation match the adapter's `KEY_PATTERN`, so unusable keys are not saved.
- Document the logging blind spots: `http.client` debuglevel and handlers attached to child loggers.

Each finding needs a regression test (RED first). Bound every wait.
