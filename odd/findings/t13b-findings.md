# T13 verification (2190cc5) - adversarial, read-only
Full suite: `scripts/check.sh` in worktree: ruff clean, 1294 passed, coverage 97.28%, all checks passed.
Repros: verify-t13-work/test_zz_verify.py (pytest-qt, fake CoverDesigner).

## Findings
1. LOW-MEDIUM, CONFIRMED - editform.py `on_design` (~l.612-616): only `DesignError` is caught around `DesignCoverWithAI(factory())`, which runs on the GUI thread.
   Repro `test_factory_raises_unexpected`: factory raising `RuntimeError('boom '+KEY)` escapes the slot (qtbot.captureExceptions got it). In production it goes to sys.excepthook / OpenLP's error dialog, with the exception text unredacted (the "type name only" guarantee holds only on the worker path), and the button state is untouched. Real make_designer rarely raises other types (store errors are mapped), so this is defensive.
   Fix: `except Exception as error:` -> log type name only; status "AI design is not available (TypeName)"; keep `DesignError` branch.
2. LOW, CONFIRMED - editform.py `_design_done`/`_design_failed` -> `_set_status`: status_label is a default (AutoText) QLabel, so AI `notes` and provider error text render as rich text. Repro `test_notes_html_spoof`: notes `<a href=..>Click</a><img src=http://evil/..>` end up in the label (textFormat=2 AutoText). Qt does not fetch remote images and links are not opened by default, so impact is spoofing/layout only.
   Fix: `status_label.setTextFormat(Qt.PlainText)` (or html.escape the AI-derived parts).
3. LOW, CONFIRMED (UX) - Picking a built-in template while a design is running: `_template_picked` clears the custom design, then the design lands and silently reinstates it (repro `test_pick_template_during_design`: custom set, template list row unchanged). Also re-clicking the already-current template does not drop the design (no currentItemChanged); only the "Use the selected template instead" button does. Suggest: cancel/ignore the in-flight job in `_template_picked`, or disable template_list while designing.
4. LOW, PLAUSIBLE - `_design_done` -> `_set_custom_icon(applied.icon)` overwrites the single "Uploaded" slot, discarding a user's uploaded icon without undo; and "Use the selected template instead" does not restore the previous icon. Document or keep the prior icon item.
5. INFO - Error text redaction relies on registered keys + key shapes. A DesignError from the provider echoing an unregistered/odd-shaped secret is shown verbatim (repro `test_design_error_with_unregistered_plain_key`). Keys read through FileSecretStore are registered (secret_store.py:120/129, http.py:88), so the normal path is covered.

## Claims found sound (tested)
- Busy state: button disabled, Cancel visible, Save disabled while running; direct `on_save()` and second `on_design()`/click ignored (one request recorded).
- Cancel then redesign quickly: old job's outcome is dropped (BackgroundJob._cancelled checked in `_deliver`), new result applied correctly (`test_cancel_then_redesign_old_callback`, status shows 2nd result).
- Close during design (`reject`) then releasing the designer: no exception, no state change.
- Callbacks are on the GUI thread (queued signal from worker; `_finished` connected in GUI thread). Exceptions in callbacks are caught in `_deliver`.
- Unexpected worker errors show only the type name; key not in status text nor in logs (caplog) (`test_unexpected_error_text`). DesignError text is redacted.
- AI never writes text: apply_to only touches custom_template_html/icon; a template with hard-coded text ("SEND MONEY TO FOO") is rejected by the sanitizer after repair round (test_ai_text_literal_in_template).
- Preview redraws with the AI template (last pending render contains the custom CSS); save persists custom_template_html; template is re-sanitized on every compose, so a stored template tampered with `<script>` is stripped on load/render.
- Picking a different built-in template (not during a design) drops the design; load_cover keeps the design and shows the note + "use template" button.
