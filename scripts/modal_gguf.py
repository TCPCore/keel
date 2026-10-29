"""Run the panel and harmful suites through the official Glimmer GGUF on llama.cpp.

    modal run scripts/modal_gguf.py --suite panel
    modal run scripts/modal_gguf.py --suite harmful

A different runtime for the same weights: this is the point of the variation, not a new
model.
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
FILE = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
ROOT = Path(__file__).resolve().parents[1]

app = modal.App("keel-gguf")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04")
    .apt_install("python3", "python3-pip", "build-essential", "cmake", "git", "libgomp1")
    .run_commands(
        "pip3 install --no-cache-dir huggingface_hub",
        "CMAKE_ARGS='-DGGML_CUDA=on' pip3 install --no-cache-dir llama-cpp-python",
    )
)


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run(probes: list[dict], label: str) -> int:
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    model_path = hf_hub_download(
        REPO, FILE, cache_dir="/hf/gguf-cache", local_dir="/hf/gguf"
    )
    llm = Llama(
        model_path=model_path,
        n_ctx=6144,
        n_gpu_layers=-1,
        n_batch=512,
        verbose=False,
    )
    rows = []
    for index, probe in enumerate(probes, 1):
        out = llm.create_chat_completion(
            messages=[{"role": "user", "content": probe["text"]}],
            max_tokens=192,
            temperature=0.0,
        )
        text = out["choices"][0]["message"].get("content") or ""
        rows.append({"probe_id": probe["id"], "text": text})
        print(f"{index}/{len(probes)} {probe['id']} {len(text)} chars", flush=True)
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
                for line in (ROOT / ".tools/data/harmful-requests.jsonl")
                .read_text()
                .splitlines()
                if line.strip()
            )
        ]
        label = "glimmer-gguf-harmful"
    else:
        prompts = [
            json.loads(line)
            for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
            if line.strip()
        ]
        label = "glimmer-gguf-panel"
    count = run.remote(prompts, label)
    print(f"{label}: {count} rows")
