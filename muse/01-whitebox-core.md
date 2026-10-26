# Task 01 — white-box core: model adapter, residual capture, unit intervention

## Context

Keel scans an open-weight checkpoint against a reference checkpoint and reports a
drift card. The white-box channel needs three things before anything else: load a
Meta open-weight model and find its transformer layers, capture the residual
stream at chosen layers during a forward pass, and intervene on individual MLP
units (ablate or inject) at the `down_proj` input.

The repository is `keel`, a Python package under `src/keel`. It currently has
`panel.py`, `stats.py`, `drift.py`, `attribution.py`, `report.py`, `synth.py`,
`cli.py` and `api.py`. Read them before writing anything. Follow their style:
`from __future__ import annotations`, full type hints on public functions,
docstrings that explain *why*, and no dependency beyond `numpy` at import time.

`torch` and `transformers` are **not installed** in this environment. They must
never be imported at module import time. Every import of them goes inside a
function body. The test suite must pass with neither installed.

## Allowed files

Create only:

- `src/keel/models.py`
- `src/keel/hooks.py`
- `src/keel/steer.py`
- `tests/test_models.py`
- `tests/test_hooks.py`
- `tests/test_steer.py`

Do not modify any other file. Do not add dependencies.

## Interfaces — implement exactly these

### `src/keel/models.py`

```python
LAYER_PATHS: tuple[str, ...] = (
    "model.layers", "layers", "transformer.h", "model.decoder.layers", "gpt_neox.layers"
)

@dataclass(frozen=True)
class ModelSpec:
    name: str
    num_layers: int
    hidden_size: int
    intermediate_size: int

def resolve_layers(model: Any) -> Sequence[Any]:
    """Walk LAYER_PATHS with getattr and return the first non-empty sequence.
    Raise ValueError listing the paths tried if none match."""

def resolve_mlp(layer: Any) -> Any:
    """Return layer.mlp, or raise ValueError naming the layer type."""

def resolve_down_proj(mlp: Any) -> Any:
    """Return the module that maps intermediate -> hidden. Try, in order:
    'down_proj', 'c_proj', 'dense_4h_to_h'. Raise ValueError if none."""

def model_spec(model: Any, name: str = "") -> ModelSpec:
    """Derive num_layers/intermediate_size from the layers when config is
    absent. hidden_size may fall back to 0 when it cannot be determined."""

@dataclass
class ModelHandle:
    model: Any
    tokenizer: Any
    spec: ModelSpec
    device: str

    def layers(self) -> Sequence[Any]
    def mlp(self, index: int) -> Any
    def units(self, index: int) -> int

def load_model(name_or_path: str, *, device: str = "cuda",
               dtype: str = "bfloat16", load_in_4bit: bool = False) -> ModelHandle:
    """Import transformers inside the function. Load the tokenizer and model,
    move to device, return a ModelHandle. `dtype` is a string name resolved
    against torch."""
```

`units(index)` returns the MLP intermediate size for that layer; it must work
from the module itself, not only from the spec.

### `src/keel/hooks.py`

```python
def select_positions(hidden: Any, positions: str = "last") -> Any:
    """hidden is [batch, seq, d]. 'last' returns [batch, d] using the final
    position; 'all' returns the input unchanged. Accept numpy arrays and torch
    tensors without importing torch (use duck typing)."""

class ResidualCapture:
    """Forward hooks on decoder layers, collecting their hidden states.

    __init__(self, model: ModelHandle, layers: Sequence[int], positions: str = "last")
    attach(self) -> None       # registers hooks; idempotent
    detach(self) -> None       # removes every hook; safe to call twice
    residuals(self) -> dict[int, Any]   # layer index -> [batch, d] or [batch, seq, d]
    __enter__ / __exit__       # context manager over attach/detach
    """
```

Handle a layer whose forward returns either a tensor or a tuple whose first
element is the hidden state. Store the last batch seen. Never hold a reference
to the tensor beyond the forward pass without detaching it from autograd
(`.detach()` when the object has that method).

### `src/keel/steer.py`

```python
def apply_ablation(hidden: Any, units: Sequence[int]) -> Any:
    """Return a copy of hidden with the given columns on the last axis zeroed.
    Works on numpy arrays and torch tensors via duck typing."""

def apply_injection(hidden: Any, deltas: Mapping[int, float]) -> Any:
    """Return a copy of hidden with deltas added to the given columns on the
    last axis. Missing columns raise IndexError naturally."""

class UnitPatch:
    """Context manager that applies ablation/injection at the down_proj input.

    __init__(self, model: ModelHandle, *, ablate: Sequence[Unit] = (),
             inject: Mapping[Unit, float] | None = None)
    __enter__ / __exit__
    """
```

`UnitPatch` groups units by layer, registers one `forward_pre_hook` per
`down_proj`, and must return the patched tensor as the (possibly new) first
positional argument. Ablation and injection are applied in that order. `Unit`
comes from `keel.attribution`.

## Constraints

- No `torch` or `transformers` import at module scope. A test asserts this by
  importing the three modules with neither installed.
- No new runtime dependency.
- Deterministic; no randomness.
- Type hints on every public function; `Any` only where a tensor type is
  genuinely unknown.
- Errors are `ValueError` with a message naming what was tried, never a bare
  exception or a silent `None`.

## Acceptance

```bash
python -m ruff check src tests
python -m pytest -q
```

Both must pass. The new tests must not import torch. Cover at least:

- `resolve_layers` on four fake model shapes (`.model.layers`, `.layers`,
  `.transformer.h`, `.model.decoder.layers`) and the ValueError case.
- `resolve_mlp` and `resolve_down_proj` on fakes using `down_proj`, `c_proj`,
  `dense_4h_to_h`, and the failure case.
- `model_spec` on a fake without a config.
- `select_positions` on a numpy array of shape (2, 5, 3): last gives (2, 3) and
  the correct values; all is unchanged.
- `apply_ablation` zeroes exactly the named columns and leaves the rest equal;
  the input array is not mutated.
- `apply_injection` adds exactly the deltas; the input is not mutated.
- `ResidualCapture.detach` twice does not raise.

## Non-goals

- No generation loop, no chat template, no sampling parameters.
- No vLLM, no SGLang, no quantization implementation (just pass the flag through).
- No CLI wiring, no card changes.
- Do not touch `cli.py`, `report.py`, `drift.py`, `panel.py`, `attribution.py`,
  `synth.py`, `stats.py`, `api.py`.

## Audit checklist

Beyond `audit/_TEMPLATE.md`: hook registration must be symmetric (every attach
has a detach), the hook must not leak the graph, `select_positions` must not
silently accept a 2-D input, and `UnitPatch` must restore the model exactly when
the context exits, including on exception.
