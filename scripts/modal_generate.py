"""Generate panel responses on Modal, one stage per run.

Both stages use the same 4-bit base, so the comparison isolates the adapter.
Results are written to a Modal volume rather than returned, because a stage can
run for longer than the function timeout and losing 30 minutes of generation to a
local error is avoidable.

    python scripts/modal_generate.py --stage m0
    python scripts/modal_generate.py --stage m2
    python scripts/modal_generate.py --stage fetch

Stages m0 and m2 run on the GPU; fetch copies the JSONL out of the volume.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import modal

BASE = "unsloth/Muse-Glimmer-30B-unsloth-bnb-4bit"
ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src/keel/data/panel-v0.1.jsonl"
ADAPTER = ".tools/m2-adapter"
MAX_NEW_TOKENS = 192

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


@app.function(
    gpu="A100-40GB",
    image=image,
    volumes={"/hf": cache, "/data": data},
    timeout=3600,
)
def generate(probes: list[dict], adapter: bool, label: str) -> int:
    os.environ["HF_HOME"] = "/hf"
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
    print(f"stage {label}: adapter={adapter} class={type(model).__name__}", flush=True)

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

    path = f"/data/responses-{label}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    data.commit()
    print(f"wrote {path} ({len(rows)} rows)", flush=True)
    return len(rows)


@app.local_entrypoint()
def main(stage: str = "m0") -> None:
    if stage == "fetch":
        print("use: modal volume get keel-data responses-m0.jsonl .tools/data/")
        return

    probes = [json.loads(line) for line in PANEL.read_text().splitlines() if line.strip()]
    rows = generate.remote(probes, stage == "m2", stage)
    print(f"stage {stage}: {rows} rows")
