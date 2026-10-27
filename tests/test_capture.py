"""Tests for keel.capture: position policy and MLP input capture."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from keel.attribution import Unit
from keel.capture import QUALIFIED_POLICIES, CapturePolicy, MLPCapture, select_activations
from keel.steer import UnitPatch


class _FakeProj:
    def __init__(self) -> None:
        self.pre_hooks: list = []
        self.removed = 0

    def register_forward_pre_hook(self, fn):  # type: ignore[no-untyped-def]
        self.pre_hooks.append(fn)

        proj = self

        class _Handle:
            def remove(_self) -> None:
                proj.removed += 1
                proj.pre_hooks.remove(fn)

        return _Handle()


def _handle(projs: dict[int, _FakeProj]) -> SimpleNamespace:
    handle = SimpleNamespace()
    layers = {i: SimpleNamespace(mlp=SimpleNamespace(down_proj=p)) for i, p in projs.items()}

    def _mlp(index: int) -> SimpleNamespace:
        return layers[index].mlp  # type: ignore[no-any-return]

    handle.mlp = _mlp
    return handle


def _forward(proj: _FakeProj, hidden: np.ndarray) -> np.ndarray:
    """Run fake pre-hooks in registration order, threading args like PyTorch."""
    args = (hidden,)
    for hook in list(proj.pre_hooks):
        result = hook(proj, args)
        if result is not None:
            args = result
    return args[0]


def _array() -> np.ndarray:
    return np.arange(2 * 5 * 3, dtype=float).reshape(2, 5, 3)


def test_all_policies_exact_values() -> None:
    hidden = _array()
    assert np.array_equal(select_activations(hidden, "prompt_last", prompt_len=5), hidden[:, 4, :])
    assert np.array_equal(select_activations(hidden, "prompt_last", prompt_len=2), hidden[:, 1, :])
    got = select_activations(hidden, "sequence_last")
    assert got.shape == (2, 3)
    assert np.array_equal(got, hidden[:, -1, :])
    got = select_activations(hidden, "mean")
    assert got.shape == (2, 3)
    assert np.array_equal(got, hidden.mean(axis=1))
    got = select_activations(hidden, "all")
    assert got.shape == (2, 5, 3)
    assert got is hidden


def test_prompt_last_rejects_bad_lengths() -> None:
    hidden = _array()
    with pytest.raises(ValueError):
        select_activations(hidden, "prompt_last", prompt_len=None)
    with pytest.raises(ValueError):
        select_activations(hidden, "prompt_last", prompt_len=0)
    with pytest.raises(ValueError):
        select_activations(hidden, "prompt_last", prompt_len=6)


def test_mean_with_and_without_prompt_len() -> None:
    hidden = _array()
    assert np.allclose(select_activations(hidden, "mean"), hidden.mean(axis=1))
    assert np.allclose(
        select_activations(hidden, "mean", prompt_len=2), hidden[:, :2, :].mean(axis=1)
    )
    assert np.allclose(
        select_activations(hidden, "mean", prompt_len=5), hidden[:, :5, :].mean(axis=1)
    )


def test_2d_input_rejected_with_shape() -> None:
    hidden = np.zeros((2, 3))
    with pytest.raises(ValueError, match=r"2, 3"):
        select_activations(hidden, "sequence_last")


def test_unknown_policy_names_valid() -> None:
    with pytest.raises(ValueError, match="prompt_last"):
        select_activations(_array(), "middle")
    assert set(QUALIFIED_POLICIES) == {"prompt_last", "sequence_last", "mean", "all"}
    with pytest.raises(ValueError, match="prompt_last"):
        CapturePolicy(positions="middle").validate()
    CapturePolicy(positions="mean").validate()


def test_attach_twice_does_not_double_register() -> None:
    proj = _FakeProj()
    cap = MLPCapture(_handle({0: proj}), [0], policy=CapturePolicy(positions="all"))
    cap.attach()
    cap.attach()
    assert len(proj.pre_hooks) == 1
    cap.detach()


def test_detach_twice_does_not_raise() -> None:
    cap = MLPCapture(_handle({0: _FakeProj()}), [0])
    cap.attach()
    cap.detach()
    cap.detach()


def test_detach_without_attach_ok() -> None:
    MLPCapture(_handle({0: _FakeProj()}), [0]).detach()


def test_reattach_clears_previous_activations() -> None:
    """A re-attached capture must not serve numbers from an earlier forward."""
    proj = _FakeProj()
    cap = MLPCapture(_handle({0: proj}), [0], policy=CapturePolicy(positions="all"))
    cap.attach()
    proj.pre_hooks[0](proj, (np.zeros((1, 2, 3)),))
    assert set(cap.activations()) == {0}
    cap.detach()
    cap.attach()
    assert cap.activations() == {}
    cap.detach()


def test_context_manager_detaches_on_exception() -> None:
    proj = _FakeProj()
    with pytest.raises(RuntimeError, match="boom"):
        with MLPCapture(_handle({0: proj}), [0], policy=CapturePolicy(positions="all")):
            assert len(proj.pre_hooks) == 1
            raise RuntimeError("boom")
    assert proj.removed == 1
    assert proj.pre_hooks == []


def test_fake_down_proj_records_policy_view() -> None:
    proj = _FakeProj()
    cap = MLPCapture(
        _handle({0: proj}),
        [0],
        policy=CapturePolicy(positions="prompt_last"),
        prompt_len=2,
    )
    cap.attach()
    hidden = _array()
    proj.pre_hooks[0](proj, (hidden,))
    out = cap.activations()
    assert set(out) == {0}
    assert np.array_equal(np.asarray(out[0]), hidden[:, 1, :])
    cap.detach()


def test_missing_layer_has_no_entry() -> None:
    proj = _FakeProj()
    other = _FakeProj()
    cap = MLPCapture(
        _handle({0: proj, 1: other}),
        [0, 1],
        policy=CapturePolicy(positions="all"),
    )
    cap.attach()
    proj.pre_hooks[0](proj, (np.zeros((2, 5, 3)),))
    assert set(cap.activations()) == {0}
    cap.detach()


def test_recorded_tensor_is_detached() -> None:
    seen: dict = {}

    class _Tensor:
        ndim = 3
        shape = (1, 2, 2)

        def __init__(self, arr: np.ndarray) -> None:
            self._arr = arr

        def __getitem__(self, key):  # type: ignore[no-untyped-def]
            return _Tensor(np.asarray(self._arr[key]))

        def detach(self) -> np.ndarray:
            seen["detached"] = True
            return self._arr

    proj = _FakeProj()
    cap = MLPCapture(
        _handle({0: proj}), [0], policy=CapturePolicy(positions="sequence_last")
    )
    cap.attach()
    proj.pre_hooks[0](proj, (_Tensor(np.zeros((1, 2, 2))),))
    assert seen.get("detached") is True
    assert isinstance(cap.activations()[0], np.ndarray)
    cap.detach()


def test_patch_first_then_capture_sees_patched() -> None:
    proj = _FakeProj()
    handle = _handle({0: proj})
    with UnitPatch(handle, ablate=[Unit(layer=0, index=0)]):
        with MLPCapture(handle, [0], policy=CapturePolicy(positions="all")) as cap:
            assert len(proj.pre_hooks) == 2
            hidden = np.ones((1, 2, 3))
            _forward(proj, hidden)
            assert np.array_equal(np.asarray(cap.activations()[0])[..., 0], np.zeros((1, 2)))
            assert np.array_equal(np.asarray(cap.activations()[0])[..., 1:], np.ones((1, 2, 2)))


def test_capture_first_then_patch_sees_original() -> None:
    proj = _FakeProj()
    handle = _handle({0: proj})
    with MLPCapture(handle, [0], policy=CapturePolicy(positions="all")) as cap:
        with UnitPatch(handle, ablate=[Unit(layer=0, index=0)]):
            assert len(proj.pre_hooks) == 2
            hidden = np.ones((1, 2, 3))
            _forward(proj, hidden)
            assert np.array_equal(np.asarray(cap.activations()[0]), hidden)
