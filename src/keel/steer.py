"""Single-unit interventions at the down_proj input.

Ablation (zeroing a column) asks whether a unit is necessary; injection
(adding a constant to a column) asks whether it is sufficient. Both operate
on a copy so the caller's activation is never mutated, and UnitPatch scopes
a set of such edits to a context so the model is restored exactly on exit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .attribution import Unit
from .models import ModelHandle, resolve_down_proj

__all__ = ["UnitPatch", "apply_ablation", "apply_injection"]


def _copy(hidden: Any) -> Any:
    clone = getattr(hidden, "clone", None)
    if callable(clone):
        return clone()
    return hidden.copy()


def apply_ablation(hidden: Any, units: Sequence[int]) -> Any:
    """Return a copy of ``hidden`` with the given last-axis columns zeroed.

    Duck-typed: numpy arrays copy via ``.copy()``, torch tensors via
    ``.clone()``. The input is never mutated.
    """
    out = _copy(hidden)
    cols = list(units)
    if cols:
        out[..., cols] = 0
    return out


def apply_injection(hidden: Any, deltas: Mapping[int, float]) -> Any:
    """Return a copy of ``hidden`` with ``deltas`` added per last-axis column.

    An out-of-range column raises IndexError from the underlying indexing,
    which is intentional: a silent clip would hide a wrong layer width. The
    input is never mutated.
    """
    out = _copy(hidden)
    for column, delta in deltas.items():
        out[..., column] = out[..., column] + delta
    return out


class UnitPatch:
    """Ablate and/or inject MLP units at each down_proj input.

    Units are grouped by layer so each affected down-projection gets exactly
    one forward pre-hook. Ablation runs before injection: a unit that is
    both ablated and injected ends at the injected value. The patched tensor
    is returned as the new first positional argument, and every hook is
    removed on context exit, including on exception.
    """

    def __init__(
        self,
        model: ModelHandle,
        *,
        ablate: Sequence[Unit] = (),
        inject: Mapping[Unit, float] | None = None,
    ) -> None:
        """Collect the edit plan; no hooks are registered until __enter__."""
        self._model = model
        self._ablate = list(ablate)
        self._inject = dict(inject) if inject is not None else {}
        self._handles: list[Any] = []

    def __enter__(self) -> UnitPatch:
        """Register one pre-hook per affected down-projection."""
        ablate_by: dict[int, list[int]] = {}
        for unit in self._ablate:
            ablate_by.setdefault(unit.layer, []).append(unit.index)
        inject_by: dict[int, dict[int, float]] = {}
        for unit, delta in self._inject.items():
            inject_by.setdefault(unit.layer, {})[unit.index] = float(delta)
        for layer in sorted(set(ablate_by) | set(inject_by)):
            proj = resolve_down_proj(self._model.mlp(layer))
            cols = tuple(ablate_by.get(layer, ()))
            deltas = dict(inject_by.get(layer, {}))

            def _pre(
                _module: Any, args: Any, _cols: tuple[int, ...] = cols,
                _deltas: dict[int, float] = deltas,
            ) -> Any:
                hidden = args[0]
                if _cols:
                    hidden = apply_ablation(hidden, _cols)
                if _deltas:
                    hidden = apply_injection(hidden, _deltas)
                return (hidden, *args[1:])

            self._handles.append(proj.register_forward_pre_hook(_pre))
        return self

    def __exit__(self, *exc: Any) -> bool:
        """Remove every pre-hook; never suppresses the with-body error."""
        for handle in self._handles:
            handle.remove()
        self._handles.clear()
        return False
