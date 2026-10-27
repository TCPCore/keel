"""Generate panel responses on Modal, one stage per run.

    python scripts/modal_generate.py --stage m0    # base, 4-bit
    python scripts/modal_generate.py --stage m2    # base + LoRA adapter
    python scripts/modal_generate.py --stage m1    # base with the refusal direction ablated

m0 and m2 isolate the adapter. m1 is a training-free weight intervention: a refusal
direction is estimated from a harmful/benign contrast set and projected out of the
residual stream at every decoder layer, which is the published single-direction result
applied as a model organism.

Results are written to a Modal volume rather than returned, because a stage can run
longer than a comfortable timeout and losing a generation pass to a local error is
avoidable.

    modal volume get keel-data responses-m1.jsonl .tools/data/
"""

from __future__ import annotations

import csv
import io
import json
import os
import urllib.request
from pathlib import Path

import modal

BASE = "unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit"
ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src/keel/data/panel-v0.1.jsonl"
ADAPTER = ".tools/m2-adapter"
MAX_NEW_TOKENS = 192
REFUSAL_LAYER = 24

ADVBENCH = (
    "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/"
    "data/advbench/harmful_behaviors.csv"
)

app = modal.App("keel-generate")

# A base image with CUDA and torch already present. Building torch from wheels in
# the image takes long enough to be preempted, and inference does not need a
# specific torch build.
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0",
        "accelerate",
        "bitsandbytes",
        "peft",
        "safetensors",
        "sentencepiece",
        "numpy",
    )
    .add_local_dir(ADAPTER, remote_path="/adapter")
)

cache = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)


def _layer_list(model):
    """Find the decoder layer list by shape, not by architecture-specific names."""
    import torch.nn as nn

    for _, module in model.named_modules():
        if isinstance(module, nn.ModuleList) and len(module) == 52:
            return module
    raise RuntimeError("could not find a 52-layer ModuleList in the model")


def _load(adapter: bool):
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BASE, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        BASE, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, "/adapter")
    model.eval()
    return model, tokenizer


def _generate(model, tokenizer, probes):
    import torch

    rows = []
    for index, probe in enumerate(probes, 1):
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": probe["text"]}],
            add_generation_prompt=True,
            tokenize=False,
            reasoning_strength="low",
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
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
        rows.append({"probe_id": probe["id"], "text": reply})
        print(f"{index}/{len(probes)} {probe['id']} {len(reply)} chars", flush=True)
    return rows


def _harmful_prompts(limit: int = 32) -> list[str]:
    """Public AdvBench goals, used only to estimate the refusal direction."""
    raw = urllib.request.urlopen(ADVBENCH, timeout=60).read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    return [row["goal"] for row in rows[:limit]]


def _refusal_direction(model, tokenizer, harmful: list[str], benign: list[str]):
    """Mean harmful minus mean benign residual at one layer, normalized."""
    import torch

    layers = _layer_list(model)
    captured: list = []

    def grab(_module, _args, output):
        hidden = output[0] if isinstance(output, tuple) else output
        captured.append(hidden[:, -1, :].detach().float().mean(dim=0))

    handle = layers[REFUSAL_LAYER].register_forward_hook(grab)

    def residuals(prompts: list[str]):
        vectors = []
        for text in prompts:
            messages = [{"role": "user", "content": text}]
            prompt = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=False,
                reasoning_strength="low",
            )
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            captured.clear()
            with torch.no_grad():
                model(**inputs)
            vectors.append(captured[-1].cpu())
        return torch.stack(vectors).mean(dim=0)

    harmful_mean = residuals(harmful)
    benign_mean = residuals(benign)
    handle.remove()

    direction = harmful_mean - benign_mean
    return direction / direction.norm()


@app.function(
    gpu="A100-40GB",
    image=image,
    volumes={"/hf": cache, "/data": data},
    timeout=3600,
)
def generate(probes: list[dict], stage: str) -> int:
    os.environ["HF_HOME"] = "/hf"
    import torch

    model, tokenizer = _load(adapter=(stage == "m2"))
    print(f"stage {stage}: loaded {type(model).__name__}", flush=True)

    handles = []
    if stage == "m1":
        harmful = _harmful_prompts()
        benign = [probe["text"] for probe in probes]
        direction = _refusal_direction(model, tokenizer, harmful, benign)
        device = next(model.parameters()).device
        vector = direction.to(device=device, dtype=torch.bfloat16)

        def ablate(_module, args):
            hidden = args[0]
            projection = (hidden * vector).sum(-1, keepdim=True) * vector
            return (hidden - projection, *args[1:])

        for layer in _layer_list(model):
            handles.append(layer.register_forward_pre_hook(ablate))
        print(f"stage m1: ablating direction at {len(handles)} layers", flush=True)

    rows = _generate(model, tokenizer, probes)

    for handle in handles:
        handle.remove()

    path = f"/data/responses-{stage}.jsonl"
    with open(path, "w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")
    data.commit()
    print(f"wrote {path} ({len(rows)} rows)", flush=True)
    return len(rows)


@app.local_entrypoint()
def main(stage: str = "m0") -> None:
    if stage == "fetch":
        print("use: modal volume get keel-data responses-m1.jsonl .tools/data/")
        return
    probes = [json.loads(line) for line in PANEL.read_text().splitlines() if line.strip()]
    rows = generate.remote(probes, stage)
    print(f"stage {stage}: {rows} rows")
