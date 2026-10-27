"""MLP input capture at the down-projection input.

Residual hooks see the decoder output after the MLP has been added back,
which hides the per-unit intermediate basis that attribution reasons
about. This module hooks the ``down_proj`` input instead, so each unit
is one last-axis column. Positions are explicit (``prompt_last`` needs
a ``prompt_len``) so a prefill run cannot silently stand in for a decode
run.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .models import ModelHandle, resolve_down_proj

__all__ = ["QUALIFIED_POLICIES", "CapturePolicy", "MLPCapture", "select_activations"]

QUALIFIED_POLICIES: tuple[str, ...] = ("prompt_last", "sequence_last", "mean", "all")


def _ndim(hidden: Any) -> int:
    """Return the dimensionality of a numpy- or torch-like hidden state."""
    ndim = getattr(hidden, "ndim", None)
    if ndim is not None:
        return int(ndim)
    try:
        return int(hidden.dim())
    except AttributeError:
        raise ValueError(
            f"expected a 3-D hidden state [batch, seq, d], got {type(hidden).__name__}"
        ) from None


def _shape(hidden: Any) -> Any:
    """Return the shape of a numpy- or torch-like hidden state."""
    return getattr(hidden, "shape", None)


def _seq_len(hidden: Any) -> int:
    """Return the sequence length (axis 1) of a 3-D hidden state."""
    shape = _shape(hidden)
    try:
        return int(shape[1])
    except (TypeError, IndexError, KeyError):
        raise ValueError(
            f"expected a 3-D hidden state [batch, seq, d], got shape {shape!r}"
        ) from None


def _mean_over_seq(hidden: Any) -> Any:
    """Mean over axis 1 for numpy- and torch-like arrays without importing torch."""
    mean = getattr(hidden, "mean", None)
    if not callable(mean):
        raise ValueError(f"cannot take the mean of {type(hidden).__name__}; no mean method")
    try:
        return hidden.mean(axis=1)
    except TypeError:
        return hidden.mean(dim=1)


def select_activations(hidden: Any, policy: str, *, prompt_len: int | None = None) -> Any:
    """Reduce [batch, seq, d] to the unit-activation view for ``policy``.

    ``"prompt_last"`` indexes ``prompt_len - 1`` on every sequence, so the
    same prompt token is read during prefill and decode. ``"sequence_last"``
    reads the final position. ``"mean"`` averages positions
    ``0..prompt_len - 1`` when ``prompt_len`` is given, else all positions.
    ``"all"`` returns the input unchanged.
    """
    if policy not in QUALIFIED_POLICIES:
        valid = ", ".join(QUALIFIED_POLICIES)
        raise ValueError(f"unknown policy {policy!r}; expected one of {valid}")
    ndim = _ndim(hidden)
    if ndim != 3:
        raise ValueError(
            f"expected a 3-D hidden state [batch, seq, d] for policy {policy!r}, "
            f"got {ndim}-D input with shape {_shape(hidden)!r}"
        )
    seq = _seq_len(hidden)
    if policy == "all":
        return hidden
    if policy == "sequence_last":
        return hidden[:, -1, :]
    if policy == "prompt_last":
        if prompt_len is None or not 1 <= prompt_len <= seq:
            raise ValueError(
                f"prompt_last requires prompt_len in 1..{seq}, got {prompt_len!r}"
            )
        return hidden[:, prompt_len - 1, :]
    # policy == "mean"
    if prompt_len is None:
        return _mean_over_seq(hidden)
    if not 1 <= prompt_len <= seq:
        raise ValueError(f"mean requires prompt_len in 1..{seq} when given, got {prompt_len!r}")
    return _mean_over_seq(hidden[:, :prompt_len, :])


@dataclass(frozen=True)
class CapturePolicy:
    """Named position policy for :class:`MLPCapture`."""

    positions: str = "prompt_last"

    def validate(self) -> None:
        """Raise ValueError unless ``positions`` names a qualified policy."""
        if self.positions not in QUALIFIED_POLICIES:
            valid = ", ".join(QUALIFIED_POLICIES)
            raise ValueError(f"unknown policy {self.positions!r}; expected one of {valid}")


class MLPCapture:
    """Forward pre-hooks on ``down_proj``, recording unit activations.

    The hook reads the pre-hook input ``args[0]`` (the intermediate basis
    individual units live in) and stores the policy-reduced view, detached
    from autograd when the object has ``.detach()``.

    Hook ordering matters because PyTorch runs forward pre-hooks in
    registration order. If a :class:`keel.steer.UnitPatch` is registered
    first, a later ``MLPCapture`` records the patched activations; if the
    capture is registered first, it records the unpatched ones. Attribution
    needs unpatched values, so the capture must be entered before any
    patch: ``with MLPCapture(...): with UnitPatch(...): ...``.
    """

    def __init__(
        self,
        model: ModelHandle,
        layers: Sequence[int],
        policy: CapturePolicy = CapturePolicy(),  # noqa: B008 - interface requires this default
        prompt_len: int | None = None,
    ) -> None:
        """Bind to ``model`` (a ModelHandle) without registering anything yet."""
        policy.validate()
        self._model = model
        self._layers = list(layers)
        self._policy = policy
        self._prompt_len = prompt_len
        self._handles: list[Any] = []
        self._store: dict[int, Any] = {}

    def attach(self) -> None:
        """Register one forward pre-hook per requested layer; idempotent."""
        if self._handles:
            return
        self._store.clear()
        for index in self._layers:
            proj = resolve_down_proj(self._model.mlp(index))

            def _pre(_module: Any, args: Any, _index: int = index) -> None:
                hidden = args[0]
                hidden = select_activations(
                    hidden, self._policy.positions, prompt_len=self._prompt_len
                )
                detach = getattr(hidden, "detach", None)
                if callable(detach):
                    hidden = detach()
                self._store[_index] = hidden

            self._handles.append(proj.register_forward_pre_hook(_pre))

    def detach(self) -> None:
        """Remove every pre-hook; safe to call twice or without attach."""
        for handle in self._handles:
            handle.remove()
        self._handles.clear()

    def activations(self) -> dict[int, Any]:
        """Return the last batch seen per layer, keyed by layer index."""
        return dict(self._store)

    def __enter__(self) -> MLPCapture:
        """Attach pre-hooks and return this capture."""
        self.attach()
        return self

    def __exit__(self, *exc: Any) -> bool:
        """Detach pre-hooks, including when the body raised; never suppresses."""
        self.detach()
        return False
