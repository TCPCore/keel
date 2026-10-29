"""Run the GGUF suite through the precompiled llama.cpp server.

    modal run scripts/modal_gguf_server.py --suite panel

No Python bindings and no compile: the image ships the server binary, we start it in the
function and talk HTTP to it.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

import modal

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
FILE = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
ROOT = Path(__file__).resolve().parents[1]

app = modal.App("keel-gguf-server")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
data = modal.Volume.from_name("keel-data", create_if_missing=True)

image = (
    modal.Image.from_registry("ghcr.io/ggerganov/llama.cpp:server-cuda")
    .apt_install("python3")
)


@app.function(gpu="A10G", image=image, volumes={"/hf": hf, "/data": data}, timeout=5400)
def run(probes: list[dict], label: str) -> int:
    import os

    model = "/hf/gguf/glimmer-q4.gguf"
    os.makedirs("/hf/gguf", exist_ok=True)
    if not os.path.exists(model):
        url = f"https://huggingface.co/{REPO}/resolve/main/{FILE}"
        print("downloading", url, flush=True)
        urllib.request.urlretrieve(url, model)
        hf.commit()

    server = subprocess.Popen(
        [
            "/app/llama-server",
            "-m",
            model,
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "-ngl",
            "99",
            "-c",
            "6144",
            "--parallel",
            "1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(120):
        try:
            urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2)
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    else:
        server.kill()
        raise RuntimeError("llama-server did not become healthy")

    rows = []
    for index, probe in enumerate(probes, 1):
        payload = json.dumps(
            {
                "messages": [{"role": "user", "content": probe["text"]}],
                "max_tokens": 192,
                "temperature": 0,
            }
        ).encode()
        request = urllib.request.Request(
            "http://127.0.0.1:8080/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read())
        text = body["choices"][0]["message"].get("content") or ""
        rows.append({"probe_id": probe["id"], "text": text})
        print(f"{index}/{len(probes)} {probe['id']} {len(text)} chars", flush=True)

    server.kill()
    path = f"/data/responses-{label}.jsonl"
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    data.commit()
    print("wrote", path, flush=True)
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
    print(run.remote(prompts, label))
