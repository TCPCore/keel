"""Tests for keel.models: layer/MLP resolution without a GPU stack."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from keel import models
from keel.models import (
    ModelHandle,
    model_spec,
    resolve_down_proj,
    resolve_layers,
    resolve_mlp,
)


def _layers(n: int = 2, *, intermediate: int = 8, hidden: int = 4) -> list:
    out = []
    for _ in range(n):
        proj = SimpleNamespace(in_features=intermediate, out_features=hidden)
        out.append(SimpleNamespace(mlp=SimpleNamespace(down_proj=proj)))
    return out


def test_no_torch_or_transformers_at_import() -> None:
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules
    for name in ("models", "hooks", "steer"):
        assert f"keel.{name}" in sys.modules or name == "models"
    import keel.hooks  # noqa: F401
    import keel.steer  # noqa: F401

    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_no_module_scope_torch_import() -> None:
    """Indented imports inside a function are fine; top-level ones are not.

    An AST walk is the only honest check here: a line-prefix test treats an
    indented `import torch` inside `load_model` as module scope and fails a
    correct file.
    """
    import ast
    import pathlib

    for name in ("models.py", "hooks.py", "steer.py"):
        tree = ast.parse((pathlib.Path(models.__file__).parent / name).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not roots & {"torch", "transformers"}, (
                f"{name}: module-scope import of {sorted(roots & {'torch', 'transformers'})}"
            )


def test_resolve_layers_model_layers() -> None:
    model = SimpleNamespace(model=SimpleNamespace(layers=_layers(3)))
    assert len(resolve_layers(model)) == 3


def test_resolve_layers_bare_layers() -> None:
    model = SimpleNamespace(layers=_layers(2))
    assert len(resolve_layers(model)) == 2


def test_resolve_layers_transformer_h() -> None:
    model = SimpleNamespace(transformer=SimpleNamespace(h=_layers(4)))
    assert len(resolve_layers(model)) == 4


def test_resolve_layers_model_decoder_layers() -> None:
    model = SimpleNamespace(model=SimpleNamespace(decoder=SimpleNamespace(layers=_layers(5))))
    assert len(resolve_layers(model)) == 5


def test_resolve_layers_skips_empty_sequence() -> None:
    model = SimpleNamespace(model=SimpleNamespace(layers=[]), layers=_layers(2))
    assert len(resolve_layers(model)) == 2


def test_resolve_layers_failure_lists_paths() -> None:
    with pytest.raises(ValueError, match="model.layers"):
        resolve_layers(SimpleNamespace())
    try:
        resolve_layers(SimpleNamespace())
    except ValueError as exc:
        for path in models.LAYER_PATHS:
            assert path in str(exc)
    else:  # pragma: no cover - guarded by the raises above
        raise AssertionError("expected ValueError")


def test_resolve_mlp_ok() -> None:
    mlp = SimpleNamespace(down_proj=SimpleNamespace())
    assert resolve_mlp(SimpleNamespace(mlp=mlp)) is mlp


def test_resolve_mlp_failure_names_type() -> None:
    class Bare:
        pass

    with pytest.raises(ValueError, match="Bare"):
        resolve_mlp(Bare())


def test_resolve_down_proj_variants() -> None:
    proj = SimpleNamespace()
    assert resolve_down_proj(SimpleNamespace(down_proj=proj)) is proj
    assert resolve_down_proj(SimpleNamespace(c_proj=proj)) is proj
    assert resolve_down_proj(SimpleNamespace(dense_4h_to_h=proj)) is proj


def test_resolve_down_proj_prefers_down_proj() -> None:
    first, second = SimpleNamespace(), SimpleNamespace()
    mlp = SimpleNamespace(down_proj=first, c_proj=second)
    assert resolve_down_proj(mlp) is first


def test_resolve_down_proj_failure() -> None:
    with pytest.raises(ValueError, match="down_proj"):
        resolve_down_proj(SimpleNamespace(other=1))


def test_model_spec_without_config() -> None:
    model = SimpleNamespace(model=SimpleNamespace(layers=_layers(3, intermediate=16, hidden=6)))
    spec = model_spec(model, name="fake")
    assert spec.name == "fake"
    assert spec.num_layers == 3
    assert spec.intermediate_size == 16
    assert spec.hidden_size == 6


def test_model_spec_hidden_falls_back_to_zero() -> None:
    proj = SimpleNamespace(in_features=12)
    layer = SimpleNamespace(mlp=SimpleNamespace(down_proj=proj))
    model = SimpleNamespace(layers=[layer])
    assert "config" not in vars(model)
    spec = model_spec(model)
    assert spec.intermediate_size == 12
    assert spec.hidden_size == 0


def test_handle_helpers_read_modules() -> None:
    layers = _layers(2, intermediate=10, hidden=5)
    model = SimpleNamespace(layers=layers)
    spec = model_spec(model, name="fake")
    handle = ModelHandle(model=model, tokenizer=None, spec=spec, device="cpu")
    assert handle.layers() == layers
    assert handle.mlp(0) is layers[0].mlp
    assert handle.units(0) == 10
    assert handle.units(1) == 10


def test_units_ignores_stale_spec() -> None:
    layers = _layers(1, intermediate=10, hidden=5)
    model = SimpleNamespace(layers=layers)
    spec = model_spec(model, name="fake")
    stale = ModelHandle(model=model, tokenizer=None, spec=spec, device="cpu")
    object.__setattr__(layers[0].mlp.down_proj, "in_features", 24)
    assert stale.units(0) == 24
