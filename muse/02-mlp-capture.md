# Task 02 - MLP input capture with an explicit position policy

## Context

Keel reads `src/keel` and follows its existing style: `from __future__ import annotations`,
type hints on public functions, docstrings that explain why, `numpy` as the only hard
dependency, and no `torch` or `transformers` import at module scope. Read
`models.py`, `hooks.py`, `steer.py` and `attribution.py` before writing anything.

Two gaps from the task 01 audit:

1. `ResidualCapture` hooks the decoder layer output, which is the residual **after** the
   MLP. Unit attribution needs the `down_proj` **input**, the intermediate activation
   basis that individual units live in. Nothing captures it yet.
2. `select_positions(..., "last")` means "last token of whatever tensor was passed".
   During a prefill that is the last prompt token; during decode it is the last generated
   token. Those are different quantities and the ambiguity would silently corrupt an
   attribution run.

This task adds MLP input capture and makes the position policy explicit.

## Allowed files

Create only:

- `src/keel/capture.py`
- `tests/test_capture.py`

Do not modify any existing file.

## Interfaces - implement exactly these

```python
QUALIFIED_POLICIES: tuple[str, ...] = ("prompt_last", "sequence_last", "mean", "all")

def select_activations(hidden: Any, policy: str, *, prompt_len: int | None = None) -> Any:
    """Reduce [batch, seq, d] to the unit-activation view.

    "prompt_last": index prompt_len - 1 on every sequence. `prompt_len` is
        required; raise ValueError if it is None or outside 1..seq.
    "sequence_last": the final position, no prompt_len needed.
    "mean": mean over positions 0..prompt_len-1 when prompt_len is given, else
        over all positions. Returns [batch, d].
    "all": return the input unchanged, [batch, seq, d].
    Unknown policy raises ValueError naming the valid ones.
    Reject 2-D input with a ValueError that says what arrived.
    """

@dataclass(frozen=True)
class CapturePolicy:
    positions: str = "prompt_last"
    def validate(self) -> None: ...   # raises ValueError for unknown policy

class MLPCapture:
    """Forward pre-hooks on down_proj, recording unit activations.

    __init__(self, model: ModelHandle, layers: Sequence[int],
             policy: CapturePolicy = CapturePolicy(),
             prompt_len: int | None = None)
    attach(self) -> None          # idempotent; clears previous activations
    detach(self) -> None          # safe twice or without attach
    activations(self) -> dict[int, Any]   # layer -> [batch, d] or [batch, seq, d]
    __enter__ / __exit__          # detach on exit, including on exception

    The hook signature is the forward pre-hook form: (module, args) -> None,
    reading args[0]. Each recorded tensor is detached from autograd when the
    object has .detach(). A layer whose pre-hook does not fire keeps no entry,
    so callers must not assume every requested layer is present.
    """
```

Use `resolve_down_proj` from `keel.models` to find the module to hook.

## Constraints

- No `torch` or `transformers` import at module scope or anywhere in the new module.
- No new dependency.
- Every public function has a type hint and a docstring.
- Errors are `ValueError` naming what was tried and what arrived.
- Deterministic, no randomness.

## Hook ordering, which must be documented and tested

`PyTorch` runs forward pre-hooks in registration order. If a `UnitPatch` from
`keel.steer` is registered first, a later `MLPCapture` records the **patched**
activations; if capture is registered first, it records the **unpatched** ones.
Attribution needs unpatched values, so the capture must be entered before any
patch. Put that rule in the `MLPCapture` docstring and prove it with a test using
fake modules whose hook lists you can invoke manually.

## Acceptance

```bash
python -m ruff check src tests
python -m pytest -q
```

Both pass, with no torch installed. Cover at least:

- `select_activations` for all four policies on a `(2, 5, 3)` numpy array, checking
  exact values, not just shapes.
- `prompt_last` with `prompt_len=None`, `0`, and `6` on a length-5 axis all raise.
- `mean` with and without `prompt_len`, checking the reduced values.
- 2-D input rejected, and the message mentions the shape that arrived.
- `MLPCapture.attach` twice does not double-register.
- `MLPCapture.detach` twice does not raise.
- Context manager detaches when the body raises.
- A fake `down_proj` records the tensor it was called with, and the captured value
  equals the input after the policy is applied.
- Hook ordering: patch first then capture sees the patched tensor; capture first
  then patch sees the original. Use fakes, not torch.

## Non-goals

- No scan wiring, no card changes, no CLI changes.
- Do not touch `models.py`, `hooks.py`, `steer.py`, `attribution.py`, `cli.py`,
  `report.py`, `drift.py`, `panel.py`, `stats.py`, `synth.py`, `api.py`.
- No generation loop, no tokenizer handling, no batching logic.

## Audit checklist

Beyond `audit/_TEMPLATE.md`: the policy is explicit at every call site, no silent
fallback from `prompt_last` to `sequence_last`, hook removal is symmetric, and the
recorded tensors cannot keep an autograd graph alive.
