"""Replay a recovered direction on the base and compare with the derivative.

    python scripts/replay.py --mode derivative
    python scripts/replay.py --mode replay

Modes:
  derivative  load the downloaded heretic checkpoint and generate
  replay      load the base BF16 and orthogonalize the recovered direction out of
              o_proj and down_proj at every layer, then generate

Both write 16 harmful-prompt responses to the Modal volume. The BF16 base responses
already exist from the M4 run, so three points come from two new runs:
base 0.00, derivative ?, replay ?.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import modal

BASE = "meta-models/Muse-Glimmer-30B"
DERIVATIVE = "/data/heretic"
ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / ".tools/data/harmful-requests.jsonl"
DIRECTION = ROOT / ".tools/svd-rows-heretic-24-28.jsonl"
LIMIT = 32
MAX_NEW_TOKENS = 192

app = modal.App("keel-replay")
vol = modal.Volume.from_name("keel-decomp", create_if_missing=True)
cache = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0",
        "accelerate",
        "bitsandbytes",
        "safetensors",
        "sentencepiece",
        "numpy",
    )
)


def _layer_list(model):
    import torch.nn as nn

    for _, module in model.named_modules():
        if isinstance(module, nn.ModuleList) and len(module) == 52:
            return module
    raise RuntimeError("no 52-layer ModuleList found")


def _refusal_direction(model, tokenizer, harmful: list[str], benign: list[str]):
    import torch

    layers = _layer_list(model)
    captured: list = []

    def grab(_module, _args, output):
        hidden = output[0] if isinstance(output, tuple) else output
        captured.append(hidden[:, -1, :].detach().float().mean(dim=0))

    handle = layers[24].register_forward_hook(grab)

    def mean_residual(prompts: list[str]):
        vectors = []
        for text in prompts:
            prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": text}],
                add_generation_prompt=True,
                tokenize=False,
                reasoning_strength="low",
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            captured.clear()
            with torch.no_grad():
                model(**inputs)
            vectors.append(captured[-1].cpu())
        return torch.stack(vectors).mean(dim=0)

    direction = mean_residual(harmful) - mean_residual(benign)
    handle.remove()
    return direction / direction.norm()


def _generate(model, tokenizer, prompts: list[dict]) -> list[dict]:
    import torch

    rows = []
    for index, item in enumerate(prompts, 1):
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": item["text"]}],
            add_generation_prompt=True,
            tokenize=False,
            reasoning_strength="low",
        )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        reply = tokenizer.decode(
            generated[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )
        rows.append({"probe_id": item["id"], "text": reply})
        print(f"{index}/{len(prompts)} {item['id']} {len(reply)} chars", flush=True)
    return rows


@app.function(
    gpu="A100-80GB",
    image=image,
    volumes={"/hf": cache, "/data": vol},
    timeout=3600,
)
def run(
    mode: str,
    prompts: list[dict],
    direction: list[list[float]] | None,
    scales: dict[str, float] | None,
    benign: list[str] | None = None,
) -> int:
    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    source = DERIVATIVE if mode == "derivative" else BASE
    tokenizer = AutoTokenizer.from_pretrained(source, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        source, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()

    if mode == "m1":
        if not benign:
            raise ValueError("m1 control needs benign contrast prompts")
        vector = _refusal_direction(
            model, tokenizer, [item["text"] for item in prompts], benign
        ).to(device=next(model.parameters()).device, dtype=torch.bfloat16)
        edited = 0
        for name, module in model.named_modules():
            if not (name.endswith("self_attn.o_proj") or name.endswith("mlp.down_proj")):
                continue
            weight = getattr(module, "weight", None)
            if weight is None or weight.shape[0] != vector.numel():
                continue
            with torch.no_grad():
                projection = torch.outer(vector.float(), vector.float() @ weight.float())
                weight.sub_(projection.to(weight.dtype))
            edited += 1
        print(f"m1 control: orthogonalized {edited} matrices", flush=True)

    if mode == "replay":
        import re

        if not direction:
            raise ValueError("replay needs the recovered direction")
        if not scales:
            raise ValueError("replay needs the per-layer scale profile")
        vector = torch.tensor(direction[0], dtype=torch.bfloat16)
        vector = vector / vector.norm()
        vector = vector.to(next(model.parameters()).device)
        edited = 0
        pattern = re.compile(r"layers\.(\d+)\.(self_attn\.o_proj|mlp\.down_proj)$")
        for name, module in model.named_modules():
            match = pattern.search(name)
            if not match:
                continue
            scale = scales.get(match.group(1), 0.0)
            if scale <= 0:
                continue
            weight = getattr(module, "weight", None)
            if weight is None or weight.shape[0] != vector.numel():
                continue
            with torch.no_grad():
                projection = torch.outer(vector.float(), (vector.float() @ weight.float()))
                weight.sub_((scale * projection).to(weight.dtype))
            edited += 1
        print(f"orthogonalized {edited} matrices using the recovered scale profile", flush=True)

    rows = _generate(model, tokenizer, prompts)
    path = f"/data/responses-{mode}-harmful{len(prompts)}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    vol.commit()
    print(f"wrote {path}", flush=True)
    return len(rows)


@app.local_entrypoint()
def main(mode: str = "derivative", multiplier: float = 1.0) -> None:
    raw = [json.loads(line) for line in REQUESTS.read_text().splitlines() if line.strip()]
    requests = [{"id": row["probe_id"], "text": row["text"]} for row in raw][:LIMIT]
    direction = None
    if mode == "replay":
        rows = [
            json.loads(line)
            for line in DIRECTION.read_text().splitlines()
            if line.strip()
        ]
        direction = [row["out_dir"] for row in rows]
        print(f"using direction from layer {rows[0]['layer']}")
    scales = None
    if mode == "replay":
        rows = [json.loads(line) for line in DIRECTION.read_text().splitlines() if line.strip()]
        peak = max(row["sigma1"] for row in rows)
        scales = {str(row["layer"]): multiplier * row["sigma1"] / peak for row in rows}
        print(f"scale profile over {len(scales)} layers, peak {peak:.4f}, multiplier {multiplier}")
    benign = None
    if mode == "m1":
        benign = [
            json.loads(line)["text"]
            for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
            if line.strip()
        ]
    count = run.remote(mode, requests, direction, scales, benign)
    print(f"{mode}: {count} rows")
