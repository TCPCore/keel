"""Generate panel or harmful responses for the heretic-plus derivative.

    python scripts/modal_plus.py --suite panel
    python scripts/modal_plus.py --suite harmful

heretic-plus is a different author's stack on the same base: structure-aware ablation
plus a targeted SFT pass. Running the gate on it tests whether the instrument finds a
second real derivative, not just the organisms we built ourselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

SOURCE = "gjtgjt/Muse-Glimmer-30B-heretic-plus"
ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "src/keel/data/panel-v0.1.jsonl"
REQUESTS = ROOT / ".tools/data/harmful-requests.jsonl"
MAX_NEW_TOKENS = 192

app = modal.App("keel-plus")
cache = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

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


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": cache, "/data": data}, timeout=5400)
def generate(probes: list[dict], label: str) -> int:
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(SOURCE, cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        SOURCE, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()
    print(f"{label}: loaded {type(model).__name__}", flush=True)

    rows = []
    for index, probe in enumerate(probes, 1):
        text = tokenizer.apply_chat_template(
            [{"role": "user", "content": probe["text"]}],
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
        rows.append({"probe_id": probe["id"], "text": reply})
        print(f"{index}/{len(probes)} {probe['id']} {len(reply)} chars", flush=True)

    path = f"/data/responses-{label}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    data.commit()
    print(f"wrote {path}", flush=True)
    return len(rows)


@app.local_entrypoint()
def main(suite: str = "panel") -> None:
    if suite == "harmful":
        prompts = [
            {"id": row["probe_id"], "text": row["text"]}
            for row in (
                json.loads(line)
                for line in REQUESTS.read_text().splitlines()
                if line.strip()
            )
        ]
        label = "plus-harmful"
    else:
        prompts = [
            json.loads(line) for line in PANEL.read_text().splitlines() if line.strip()
        ]
        label = "plus-panel"
    count = generate.remote(prompts, label)
    print(f"{label}: {count} rows")
