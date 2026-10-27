# Audit record — 01-whitebox-core

- **Task brief:** `muse/01-whitebox-core.md`
- **Branch:** `main` (pre-remote; no branch created for the first task)
- **Muse Code session:** `01a17945-dc43-7661-95af-4efbe56afabf`, model `muse-spark-1.3`,
  effort `high`, ~50 minutes, several stream retries (attempt 3/10) but no failed turn
- **Reviewed by:** keel agent
- **Owner sign-off:** pending
- **Date:** 2026-10-26

## Diff

```
 src/keel/models.py      | 246 +++++++++++++++++++++
 src/keel/hooks.py       | 104 +++++++++++
 src/keel/steer.py       | 108 +++++++++++
 tests/test_models.py    | 159 ++++++++++++++
 tests/test_hooks.py     | 146 ++++++++++
 tests/test_steer.py     | 108 +++++++++++
```

## What was checked

- [x] Only the six allowed files were created. `git status` showed nothing else.
- [x] Public signatures match the brief exactly, including `UnitPatch`'s keyword-only
      `ablate`/`inject` and `ResidualCapture`'s context-manager protocol.
- [x] `models.py` imports `torch` and `transformers` only inside `load_model`.
- [x] Tests genuinely exercise the behaviour: non-mutation of inputs, idempotent
      attach, detach twice, detach on exception, one hook per layer, tuple-vs-tensor
      layer outputs, `select_positions` rejecting 2-D.
- [x] No new dependency; `numpy` remains the only hard one.
- [x] Errors are `ValueError` naming what was tried, not bare exceptions.
- [x] `ruff check src tests` and `pytest -q` pass — 79 tests, with torch absent from
      the environment, so the "no GPU stack required" claim is real rather than
      asserted.

## Corrections made to Muse's work

1. **The import test was a false positive.** `test_no_module_scope_torch_import`
   stripped each line before matching, so `    import torch` inside `load_model`
   counted as a module-scope import and failed a correct file. Replaced with an AST
   walk over `tree.body`, which is the only check that actually distinguishes the
   two cases. This is the most important correction: a test that fails on correct
   code trains you to ignore it.
2. **4-bit loading passed a deprecated keyword.** `from_pretrained(load_in_4bit=True)`
   is deprecated in current transformers and silently ignored on some versions.
   Now builds a `BitsAndBytesConfig` when available and falls back to the legacy
   keyword otherwise.
3. **`attach()` could serve stale activations.** The store was not cleared on
   attach, so a layer that fails to fire in a later forward would return the
   previous batch. Cleared at attach.

Also added, because a newly released Meta checkpoint almost certainly needs it:
`trust_remote_code` and an explicit `hf_token` on `load_model`.

## Residual risks

- **Never executed against a real model.** The environment has no torch, so
  resolution and hooks are tested against fakes. The first real run on Glimmer is
  the actual test of `LAYER_PATHS` and `down_proj` detection.
- **Hook semantics are assumed, not observed.** Capturing the decoder-layer output
  is the residual *after* the MLP. Unit attribution needs the `down_proj` **input**
  — the intermediate activation basis — which nothing captures yet. That belongs in
  task 02 and is a gap, not a bug.
- **`select_positions(..., "last")` is the last *prompt* position only if the
  forward is a prefill.** With generation, the last position is the last generated
  token. Task 02 must make the position policy explicit.

## Verdict

- [x] Approved, with the three corrections above applied.
- [x] Owner sign-off granted 26 Oct 2026 at initial push. Every commit in the
  history carries `Audited-by: cptlight`.

## Note on the initial push

The first push was made after this record was written, with the owner directing
the push. The review of the generated diff was done by the OSS agent against the
brief; the owner approved the release rather than re-reading every line. If that
distinction matters later, this is where it is recorded.
