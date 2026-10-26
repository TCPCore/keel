"""Model loading and structural resolution for the white-box channel.

This module answers one question: given an opaque HF-style model object,
where are the transformer layers and how big are they. Everything else
(capture, attribution, steering) builds on these coordinates, so the
resolvers here fail loudly with the paths they tried instead of guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

LAYER_PATHS: tuple[str, ...] = (
    "model.layers",
    "layers",
    "transformer.h",
    "model.decoder.layers",
    "gpt_neox.layers",
)

_DOWN_PROJ_NAMES: tuple[str, ...] = ("down_proj", "c_proj", "dense_4h_to_h")

__all__ = [
    "LAYER_PATHS",
    "ModelHandle",
    "ModelSpec",
    "load_model",
    "model_spec",
    "resolve_down_proj",
    "resolve_layers",
    "resolve_mlp",
]


@dataclass(frozen=True)
class ModelSpec:
    """Structural facts the rest of the channel needs."""

    name: str
    num_layers: int
    hidden_size: int
    intermediate_size: int


def _walk(model: Any, path: str) -> tuple[bool, Any]:
    """Follow a dotted attribute path; return (found, value)."""
    current = model
    for part in path.split("."):
        current = getattr(current, part, None)
        if current is None:
            return False, None
    return True, current


def resolve_layers(model: Any) -> Sequence[Any]:
    """Walk LAYER_PATHS with getattr and return the first non-empty sequence.

    Raises ValueError listing every path tried when none matches, so a new
    architecture fails with a pointer instead of an AttributeError.
    """
    for path in LAYER_PATHS:
        found, candidate = _walk(model, path)
        if not found:
            continue
        try:
            size = len(candidate)  # type: ignore[arg-type]
        except TypeError:
            continue
        if size == 0:
            continue
        return candidate
    tried = ", ".join(LAYER_PATHS)
    raise ValueError(f"no transformer layers found; tried {tried}")


def resolve_mlp(layer: Any) -> Any:
    """Return the MLP submodule of one decoder layer."""
    mlp = getattr(layer, "mlp", None)
    if mlp is None:
        raise ValueError(f"layer of type {type(layer).__name__} has no 'mlp' attribute")
    return mlp


def resolve_down_proj(mlp: Any) -> Any:
    """Return the module that maps intermediate -> hidden.

    Tries 'down_proj', 'c_proj', then 'dense_4h_to_h' so Llama-style,
    GPT-2-style, and Falcon-style blocks all resolve.
    """
    for name in _DOWN_PROJ_NAMES:
        module = getattr(mlp, name, None)
        if module is not None:
            return module
    tried = ", ".join(_DOWN_PROJ_NAMES)
    raise ValueError(f"mlp of type {type(mlp).__name__} has no down-projection; tried {tried}")


def _config_int(config: Any, names: Sequence[str]) -> int | None:
    for name in names:
        value = getattr(config, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _proj_int(proj: Any, names: Sequence[str]) -> int | None:
    for name in names:
        value = getattr(proj, name, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return int(value)
    weight = getattr(proj, "weight", None)
    shape = getattr(weight, "shape", None)
    if shape is not None:
        try:
            dims = tuple(int(d) for d in shape)
        except (TypeError, ValueError):
            dims = ()
        if len(dims) == 2:
            if names and names[0] == "in_features":
                return dims[1]
            return dims[0]
    return None


def model_spec(model: Any, name: str = "") -> ModelSpec:
    """Describe a model from its layers, using config only when present.

    ``num_layers`` is always ``len(resolve_layers(model))`` so the count
    cannot disagree with what hooks will see. ``intermediate_size`` comes
    from config when available and otherwise from the first layer whose
    down-projection reports a width. ``hidden_size`` falls back to 0 when
    neither source knows it, because some fakes and partial checkpoints
    simply do not carry it.
    """
    layers = resolve_layers(model)
    num_layers = len(layers)
    config = getattr(model, "config", None)

    intermediate: int | None = None
    hidden: int | None = None
    if config is not None:
        intermediate = _config_int(
            config, ("intermediate_size", "n_inner", "ffn_dim", "d_ff")
        )
        hidden = _config_int(config, ("hidden_size", "n_embd", "d_model", "model_dim"))

    if intermediate is None:
        for layer in layers:
            try:
                proj = resolve_down_proj(resolve_mlp(layer))
            except ValueError:
                continue
            intermediate = _proj_int(proj, ("in_features",))
            if intermediate is not None:
                break
    if hidden is None:
        for layer in layers:
            try:
                proj = resolve_down_proj(resolve_mlp(layer))
            except ValueError:
                continue
            hidden = _proj_int(proj, ("out_features",))
            if hidden is not None:
                break
    if intermediate is None:
        raise ValueError("could not determine intermediate_size from config or layers")
    return ModelSpec(
        name=name,
        num_layers=num_layers,
        hidden_size=int(hidden) if hidden is not None else 0,
        intermediate_size=int(intermediate),
    )


@dataclass
class ModelHandle:
    """A loaded model plus its tokenizer and structural spec."""

    model: Any
    tokenizer: Any
    spec: ModelSpec
    device: str

    def layers(self) -> Sequence[Any]:
        """Return the decoder layers of the wrapped model."""
        return resolve_layers(self.model)

    def mlp(self, index: int) -> Any:
        """Return the MLP submodule of layer ``index``."""
        return resolve_mlp(self.layers()[index])

    def units(self, index: int) -> int:
        """Return the MLP intermediate size for layer ``index``.

        Reads the width off the down-projection module itself so the answer
        stays correct even when the spec was built from config defaults.
        """
        proj = resolve_down_proj(self.mlp(index))
        width = _proj_int(proj, ("in_features",))
        if width is not None:
            return int(width)
        if self.spec.intermediate_size:
            return int(self.spec.intermediate_size)
        raise ValueError(f"could not determine units for layer {index}")


def load_model(
    name_or_path: str,
    *,
    device: str = "cuda",
    dtype: str = "bfloat16",
    load_in_4bit: bool = False,
    trust_remote_code: bool = False,
    hf_token: str | None = None,
) -> ModelHandle:
    """Load a tokenizer and causal LM, move it to ``device``, describe it.

    ``transformers`` and ``torch`` are imported here, never at module scope,
    so the package imports without a GPU stack. ``dtype`` names a ``torch``
    dtype and is resolved with getattr.

    4-bit loading builds a ``BitsAndBytesConfig`` when the installed
    transformers has one, and falls back to the legacy keyword otherwise:
    passing ``load_in_4bit=True`` straight to ``from_pretrained`` is
    deprecated and, on some versions, ignored. ``trust_remote_code`` is
    required for architectures that ship their own modelling file, which is
    the likely case for a newly released Meta checkpoint.
    """
    import torch
    import transformers

    torch_dtype = getattr(torch, dtype, None)
    if torch_dtype is None:
        raise ValueError(f"unknown torch dtype {dtype!r}")

    tokenizer = transformers.AutoTokenizer.from_pretrained(
        name_or_path, trust_remote_code=trust_remote_code, token=hf_token
    )
    kwargs: dict[str, Any] = {
        "torch_dtype": torch_dtype,
        "trust_remote_code": trust_remote_code,
        "token": hf_token,
    }
    if load_in_4bit:
        config_cls = getattr(transformers, "BitsAndBytesConfig", None)
        if config_cls is not None:
            kwargs["quantization_config"] = config_cls(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch_dtype,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        else:  # pragma: no cover - legacy transformers only
            kwargs["load_in_4bit"] = True

    model = transformers.AutoModelForCausalLM.from_pretrained(name_or_path, **kwargs)
    if hasattr(model, "to"):
        model.to(device)
    spec = model_spec(model, name=name_or_path)
    return ModelHandle(model=model, tokenizer=tokenizer, spec=spec, device=device)
