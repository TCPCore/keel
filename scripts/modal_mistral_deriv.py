"""Mistral abliterated derivative, downloaded without huggingface_hub.

The xet backend fails on this repository, so the files are pulled with plain HTTPS and
the model is loaded from a local directory.

    modal run scripts/modal_mistral_deriv.py
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import modal

REPO = "evolveon/Mistral-7B-Instruct-v0.3-abliterated"
LOCAL = "/hf/mistral-abl"
LABEL = "mistral-abl"
ROOT = Path(__file__).resolve().parents[1]

app = modal.App("keel-mistral")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime")
    .pip_install("transformers", "accelerate", "safetensors", "sentencepiece")
)


def _download() -> str:
    os.makedirs(LOCAL, exist_ok=True)
    with urllib.request.urlopen(
        f"https://huggingface.co/api/models/{REPO}?blobs=true", timeout=60
    ) as response:
        listing = json.load(response)
    names = [
        s["rfilename"]
        for s in listing["siblings"]
        if s["rfilename"].endswith((".json", ".safetensors", ".model", ".txt"))
        and not s["rfilename"].startswith(".")
    ]
    for name in names:
        target = os.path.join(LOCAL, name)
        if os.path.exists(target):
            continue
        print("fetch", name, flush=True)
        urllib.request.urlretrieve(
            f"https://huggingface.co/{REPO}/resolve/main/{name}", target
        )
    hf.commit()
    return LOCAL


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run(panel: list[dict], harmful: list[dict], suite: str) -> int:
    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    local = _download()
    tokenizer = AutoTokenizer.from_pretrained(local)
    model = AutoModelForCausalLM.from_pretrained(
        local, device_map="auto", torch_dtype=torch.bfloat16
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

    if suite == "both":
        jobs = (("panel", panel), ("harmful", harmful))
    else:
        jobs = ((suite, panel if suite == "panel" else harmful),)
    for name, prompts in jobs:
        rows = generate(prompts, name)
        path = f"/data/responses-{LABEL}-{name}.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
        data.commit()
        print("wrote", path, flush=True)
    return 0


@app.local_entrypoint()
def main(suite: str = "both") -> None:
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
    print(run.remote(panel, harmful, suite))
