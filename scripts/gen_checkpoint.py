"""Generate the harmful suite for an abliterated checkpoint.

    modal run scripts/gen_checkpoint.py --model <repo> --label <slug> --size small|large
"""

from __future__ import annotations

import json
import pathlib

import modal

ROOT = pathlib.Path(__file__).resolve().parents[1]
app = modal.App("keel-gen-checkpoint")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)
image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install(
        "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece", "huggingface_hub"
    )
    .add_local_file(".tools/data/harmful-requests.jsonl", "/app/harmful.jsonl")
)


def _load(model_id: str, tokenizer_id: str):
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tokenizer_id, cache_dir="/hf")
    cls = AutoModelForImageTextToText if "Glimmer" in model_id else AutoModelForCausalLM
    model = cls.from_pretrained(
        model_id, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()
    return model, tokenizer


def _generate(model, tokenizer, glimmer: bool) -> list[dict]:
    import torch

    prompts = [json.loads(line) for line in open("/app/harmful.jsonl") if line.strip()]
    rows = []
    for i, prompt in enumerate(prompts, 1):
        kwargs = {"reasoning_strength": "low"} if glimmer else {}
        try:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt["text"]}],
                add_generation_prompt=True,
                tokenize=False,
                **kwargs,
            )
        except TypeError:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt["text"]}],
                add_generation_prompt=True,
                tokenize=False,
            )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=192, do_sample=False, pad_token_id=tokenizer.eos_token_id
            )
        reply = tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)
        rows.append({"probe_id": prompt["probe_id"], "text": reply})
        if i % 8 == 0:
            print(f"{i}/{len(prompts)}", flush=True)
    return rows


@app.function(gpu="A100-40GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def small(model_id: str, label: str, tokenizer_id: str) -> str:
    model, tokenizer = _load(model_id, tokenizer_id)
    rows = _generate(model, tokenizer, "Glimmer" in model_id)
    with open(f"/data/responses-{label}-harmful.jsonl", "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    data.commit()
    return f"{label}: {len(rows)} rows"


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def large(model_id: str, label: str, tokenizer_id: str) -> str:
    model, tokenizer = _load(model_id, tokenizer_id)
    rows = _generate(model, tokenizer, "Glimmer" in model_id)
    with open(f"/data/responses-{label}-harmful.jsonl", "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    data.commit()
    return f"{label}: {len(rows)} rows"


@app.local_entrypoint()
def main(model: str, label: str, size: str = "small", tokenizer: str = "") -> None:
    tokenizer_id = tokenizer or model
    if size == "large":
        print(large.remote(model, label, tokenizer_id))
    else:
        print(small.remote(model, label, tokenizer_id))
