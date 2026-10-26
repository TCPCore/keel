"""Tests for keel.hooks: position selection and residual capture."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from keel.hooks import ResidualCapture, select_positions


class _FakeLayer:
    def __init__(self) -> None:
        self.hooks: list = []
        self.removed = 0

    def register_forward_hook(self, fn):  # type: ignore[no-untyped-def]
        self.hooks.append(fn)

        class _Handle:
            def remove(_self) -> None:
                self.removed += 1

        return _Handle()


class _FakeHandle:
    def __init__(self, layers: list[_FakeLayer]) -> None:
        self._layers = layers

    def layers(self) -> list[_FakeLayer]:
        return self._layers


def _capture_with(output: object, positions: str = "last") -> dict:
    layer = _FakeLayer()
    cap = ResidualCapture(_FakeHandle([layer]), [0], positions=positions)
    cap.attach()
    assert len(layer.hooks) == 1
    layer.hooks[0](layer, (), output)
    out = cap.residuals()
    cap.detach()
    return out


def test_select_positions_last_values() -> None:
    hidden = np.arange(2 * 5 * 3, dtype=float).reshape(2, 5, 3)
    got = select_positions(hidden, "last")
    assert got.shape == (2, 3)
    assert np.array_equal(got, hidden[:, -1, :])


def test_select_positions_all_unchanged() -> None:
    hidden = np.zeros((2, 5, 3))
    assert select_positions(hidden, "all") is hidden


def test_select_positions_rejects_2d() -> None:
    with pytest.raises(ValueError, match="3-D"):
        select_positions(np.zeros((2, 3)), "last")


def test_select_positions_rejects_bad_name() -> None:
    with pytest.raises(ValueError, match="positions"):
        select_positions(np.zeros((2, 5, 3)), "middle")


def test_capture_tensor_output() -> None:
    hidden = np.arange(2 * 4 * 3, dtype=float).reshape(2, 4, 3)
    out = _capture_with(hidden)
    assert set(out) == {0}
    assert out[0].shape == (2, 3)
    assert np.array_equal(np.asarray(out[0]), hidden[:, -1, :])


def test_capture_tuple_output_uses_first_element() -> None:
    hidden = np.arange(2 * 4 * 3, dtype=float).reshape(2, 4, 3)
    out = _capture_with((hidden, {"extra": True}))
    assert np.array_equal(np.asarray(out[0]), hidden[:, -1, :])


def test_capture_all_positions_keeps_seq() -> None:
    hidden = np.zeros((2, 4, 3))
    out = _capture_with(hidden, positions="all")
    assert np.asarray(out[0]).shape == (2, 4, 3)


def test_capture_detaches_graph() -> None:
    seen: dict = {}

    class _Tensor:
        def __init__(self, arr: np.ndarray) -> None:
            self._arr = arr

        @property
        def ndim(self) -> int:
            return 3

        def __getitem__(self, key):  # type: ignore[no-untyped-def]
            return _Tensor(np.asarray(self._arr[key]))

        def detach(self) -> np.ndarray:
            seen["detached"] = True
            return self._arr

    arr = np.zeros((1, 2, 2))
    out = _capture_with(_Tensor(arr))
    assert seen.get("detached") is True
    assert isinstance(out[0], np.ndarray)


def test_attach_is_idempotent() -> None:
    layer = _FakeLayer()
    cap = ResidualCapture(_FakeHandle([layer]), [0])
    cap.attach()
    cap.attach()
    assert len(layer.hooks) == 1
    cap.detach()


def test_detach_twice_does_not_raise() -> None:
    cap = ResidualCapture(_FakeHandle([_FakeLayer()]), [0])
    cap.attach()
    cap.detach()
    cap.detach()


def test_detach_without_attach_ok() -> None:
    ResidualCapture(_FakeHandle([_FakeLayer()]), [0]).detach()


def test_context_manager_detaches() -> None:
    layer = _FakeLayer()
    handle = SimpleNamespace(layers=lambda: [layer])
    with ResidualCapture(handle, [0]) as cap:
        assert len(layer.hooks) == 1
        layer.hooks[0](layer, (), np.zeros((1, 2, 2)))
        assert 0 in cap.residuals()
    assert layer.removed == 1


def test_context_manager_detaches_on_exception() -> None:
    layer = _FakeLayer()
    handle = SimpleNamespace(layers=lambda: [layer])
    with pytest.raises(RuntimeError, match="boom"):
        with ResidualCapture(handle, [0]):
            raise RuntimeError("boom")
    assert layer.removed == 1
