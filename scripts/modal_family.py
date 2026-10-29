"""Generate panel and harmful responses for any small chat model.

    modal run scripts/modal_family.py \
        --model mistralai/Mistral-7B-Instruct-v0.3 --label mistral-base

One load, two suites, two files. Used for natural derivatives in new families.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]

app = modal.App("keel-family")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install("transformers", "accelerate", "safetensors", "sentencepiece")
    .env({"HF_HUB_DISABLE_XET": "1"})
    .run_commands("pip uninstall -y hf-xet || true")
)


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run(model_id: str, label: str, panel: list[dict], harmful: list[dict]) -> dict:
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir="/hf")
    model = AutoModelForCausalLM.from_pretrained(
        model_id, cache_dir="/hf", device_map="auto", torch_dtype=torch.bfloat16
    )
    model.eval()

    def generate(prompts, tag):
        rows = []
        for index, prompt in enumerate(prompts, 1):
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt["text"]}],
                add_generation_prompt=True,
                tokenize=False,
            )
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=192,
                    do_sample=False,
                    pad_token_id=tokenizer.eos_token_id,
                )
            reply = tokenizer.decode(
                out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
            )
            rows.append({"probe_id": prompt["id"], "text": reply})
            print(f"{tag} {index}/{len(prompts)}", flush=True)
        return rows

    for suite, prompts in (("panel", panel), ("harmful", harmful)):
        rows = generate(prompts, suite)
        path = f"/data/responses-{label}-{suite}.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        data.commit()
        print("wrote", path, flush=True)
    return {"model": model_id, "label": label}


@app.local_entrypoint()
def main(model: str = "mistralai/Mistral-7B-Instruct-v0.3", label: str = "mistral-base") -> None:
    panel = [
        json.loads(line)
        for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
        if line.strip()
    ]
    harmful = [
        {"id": row["probe_id"], "text": row["text"]}
        for row in (
            json.loads(line)
            for line in (ROOT / ".tools/data/harmful-requests.jsonl").read_text().splitlines()
            if line.strip()
        )
    ]
    print(run.remote(model, label, panel, harmful))
