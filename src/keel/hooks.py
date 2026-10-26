"""Residual-stream capture at chosen decoder layers.

Capture exists so drift can be tied to internal states, not just scores.
Hooks are registered symmetrically (every attach has a detach) and stored
activations are detached from autograd at capture time so a long scan does
not pin the graph.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

__all__ = ["ResidualCapture", "select_positions"]


def select_positions(hidden: Any, positions: str = "last") -> Any:
    """Select positions from a [batch, seq, d] hidden state.

    ``"last"`` returns the final position as [batch, d]; ``"all"`` returns
    the input unchanged. Only 3-D inputs are accepted: a 2-D array here is
    almost always a caller that already sliced, and accepting it would hide
    a double-select. Duck-typed so numpy arrays and torch tensors both work
    without importing torch.
    """
    if positions not in ("last", "all"):
        raise ValueError(f"unknown positions {positions!r}; expected 'last' or 'all'")
    ndim = getattr(hidden, "ndim", None)
    if ndim is None:
        try:
            ndim = hidden.dim()
        except AttributeError:
            raise ValueError(
                f"expected a 3-D hidden state [batch, seq, d], got {type(hidden).__name__}"
            ) from None
    if ndim != 3:
        raise ValueError(f"expected a 3-D hidden state [batch, seq, d], got {ndim}-D input")
    if positions == "all":
        return hidden
    return hidden[:, -1, :]


class ResidualCapture:
    """Forward hooks on decoder layers, collecting their hidden states.

    Each hook keeps only the most recent batch so memory stays flat across
    a scan, and each stored tensor is detached from autograd at capture
    time so the graph can be freed between forwards.
    """

    def __init__(
        self, model: Any, layers: Sequence[int], positions: str = "last"
    ) -> None:
        """Bind to ``model`` (a ModelHandle) without registering anything yet."""
        if positions not in ("last", "all"):
            raise ValueError(f"unknown positions {positions!r}; expected 'last' or 'all'")
        self._model = model
        self._layers = list(layers)
        self._positions = positions
        self._handles: list[Any] = []
        self._store: dict[int, Any] = {}

    def attach(self) -> None:
        """Register one forward hook per requested layer; idempotent."""
        if self._handles:
            return
        self._store.clear()
        modules = self._model.layers()
        for index in self._layers:
            module = modules[index]

            def _hook(_module: Any, _args: Any, output: Any, _index: int = index) -> None:
                if isinstance(output, (tuple, list)) and output:
                    hidden = output[0]
                else:
                    hidden = output
                hidden = select_positions(hidden, self._positions)
                detach = getattr(hidden, "detach", None)
                if callable(detach):
                    hidden = detach()
                self._store[_index] = hidden

            self._handles.append(module.register_forward_hook(_hook))

    def detach(self) -> None:
        """Remove every hook; safe to call twice or without attach."""
        for handle in self._handles:
            handle.remove()
        self._handles.clear()

    def residuals(self) -> dict[int, Any]:
        """Return the last batch seen per layer, keyed by layer index."""
        return dict(self._store)

    def __enter__(self) -> ResidualCapture:
        """Attach hooks and return this capture."""
        self.attach()
        return self

    def __exit__(self, *exc: Any) -> bool:
        """Detach hooks, including when the body raised; never suppresses."""
        self.detach()
        return False
