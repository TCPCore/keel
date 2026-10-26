"""Tests for keel.steer: ablation, injection, and UnitPatch."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from keel.attribution import Unit
from keel.steer import UnitPatch, apply_ablation, apply_injection


class _FakeProj:
    def __init__(self) -> None:
        self.pre_hooks: list = []
        self.removed = 0

    def register_forward_pre_hook(self, fn):  # type: ignore[no-untyped-def]
        self.pre_hooks.append(fn)

        class _Handle:
            def remove(_self) -> None:
                self.removed += 1

        return _Handle()


def _handle(projs: dict[int, _FakeProj]) -> SimpleNamespace:
    def mlp(index: int) -> SimpleNamespace:
        return SimpleNamespace(down_proj=None)

    handle = SimpleNamespace()
    layers = {i: SimpleNamespace(mlp=SimpleNamespace(down_proj=p)) for i, p in projs.items()}

    def _mlp(index: int) -> SimpleNamespace:
        return layers[index].mlp  # type: ignore[no-any-return]

    handle.mlp = _mlp
    void = mlp
    assert void is not None
    return handle


def test_ablation_zeroes_named_columns() -> None:
    hidden = np.array([[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]])
    before = hidden.copy()
    out = apply_ablation(hidden, [1, 3])
    assert np.array_equal(out[:, 0], [1.0, 5.0])
    assert np.array_equal(out[:, 1], [0.0, 0.0])
    assert np.array_equal(out[:, 2], [3.0, 7.0])
    assert np.array_equal(out[:, 3], [0.0, 0.0])
    assert np.array_equal(hidden, before)


def test_ablation_empty_is_a_copy() -> None:
    hidden = np.array([[1.0, 2.0]])
    out = apply_ablation(hidden, [])
    assert np.array_equal(out, hidden)
    assert out is not hidden


def test_injection_adds_deltas() -> None:
    hidden = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    before = hidden.copy()
    out = apply_injection(hidden, {0: 10.0, 2: -1.5})
    assert np.array_equal(out[:, 0], [11.0, 14.0])
    assert np.array_equal(out[:, 1], [2.0, 5.0])
    assert np.allclose(out[:, 2], [1.5, 4.5])
    assert np.array_equal(hidden, before)


def test_injection_missing_column_raises() -> None:
    with pytest.raises(IndexError):
        apply_injection(np.zeros((2, 2)), {5: 1.0})


def test_unit_patch_applies_ablation_then_injection() -> None:
    proj = _FakeProj()
    handle = _handle({2: proj})
    units = [Unit(layer=2, index=0), Unit(layer=2, index=1)]
    with UnitPatch(handle, ablate=units, inject={Unit(layer=2, index=1): 5.0}):
        assert len(proj.pre_hooks) == 1
        hidden = np.array([[1.0, 2.0, 3.0]])
        (patched, *_rest) = proj.pre_hooks[0](proj, (hidden,))
        # col 0 ablated to 0; col 1 ablated then injected to 5; col 2 untouched.
        assert np.array_equal(patched, np.array([[0.0, 5.0, 3.0]]))
        assert np.array_equal(hidden, np.array([[1.0, 2.0, 3.0]]))
    assert proj.removed == 1


def test_unit_patch_groups_one_hook_per_layer() -> None:
    projs = {0: _FakeProj(), 3: _FakeProj()}
    handle = _handle(projs)
    with UnitPatch(
        handle,
        ablate=[Unit(layer=0, index=1)],
        inject={Unit(layer=3, index=2): 1.0},
    ):
        assert len(projs[0].pre_hooks) == 1
        assert len(projs[3].pre_hooks) == 1
    assert projs[0].removed == 1
    assert projs[3].removed == 1


def test_unit_patch_restores_on_exception() -> None:
    proj = _FakeProj()
    handle = _handle({1: proj})
    with pytest.raises(RuntimeError, match="boom"):
        with UnitPatch(handle, ablate=[Unit(layer=1, index=0)]):
            assert len(proj.pre_hooks) == 1
            raise RuntimeError("boom")
    assert proj.removed == 1
    assert proj.pre_hooks[0](proj, (np.array([[9.0, 9.0]]),))[0].shape == (1, 2)
