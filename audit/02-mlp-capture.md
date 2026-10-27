# Audit record - 02-mlp-capture

- **Task brief:** `muse/02-mlp-capture.md`
- **Muse Code session:** `01a17c20-a737-7f80-a0c7-50edb7619e15`, model `muse-spark-1.3`,
  effort `high`
- **Reviewed by:** OSS agent
- **Owner sign-off:** `Audited-by: cptlight` on the commit
- **Date:** 2026-10-26

## Diff

```
 src/keel/capture.py   | 183 ++++++++++++++++++++++++
 tests/test_capture.py | 232 ++++++++++++++++++++++++
```

Two files, both permitted. No existing file was modified.

## What was checked

- [x] The module imports no `torch` or `transformers` anywhere, at any scope.
- [x] `select_activations` rejects 2-D input and names the shape that arrived.
- [x] `prompt_last` requires `prompt_len` and rejects `None`, `0`, and out-of-range.
      There is no silent fallback to `sequence_last`, which was the point of the task.
- [x] `mean` honours a supplied `prompt_len` and averages only the prompt slice.
- [x] The pre-hook reads `args[0]`, returns `None`, and therefore does not alter the
      forward pass.
- [x] `attach` is idempotent, `detach` is safe twice or without attach, and the context
      manager detaches on exception.
- [x] Recorded tensors are detached when the object supports `.detach()`.
- [x] A layer whose hook does not fire leaves no entry, so callers cannot assume the
      store is complete.
- [x] Hook ordering is documented in the class docstring and tested in both directions
      with the real `UnitPatch`: patch first records patched values, capture first
      records the original.

The tests are stronger than the brief required. They implement a fake pre-hook runner
that threads `args` the way PyTorch does, rather than calling hooks in isolation, so the
ordering test exercises the actual cooperative behaviour instead of asserting on a mock.

## Corrections made

1. **Missing test for the re-attach case.** The brief required `attach` to clear previous
   activations. The implementation does clear the store, but nothing proved it, so a
   future refactor could have reintroduced stale values silently. Added
   `test_reattach_clears_previous_activations`.

No implementation changes were needed. The module passed review as generated.

## Residual risks

- **Never executed against a real model.** The hooks are exercised against fakes. The
  first real run on a 3B checkpoint is the actual test of `down_proj` resolution and of
  whether the recorded tensor is the expected intermediate basis.
- **`prompt_len` is fixed at construction.** A forward whose sequence is shorter than
  `prompt_len` raises from inside the model call, which is deliberate but means one
  capture instance is bound to one prompt length. The scan must construct it per batch.
- **Decode steps re-read the prompt token.** During generation the hook fires on every
  step and `prompt_last` indexes the same position each time, so the store ends at the
  original prompt activation. That is correct and intentional, but it does mean the hook
  does redundant work while decoding.

## Verdict

- [x] Approved with one added test.
- [x] Ready for the first real checkpoint job.
