"""Download the ungated Spark Open abliterated IQ1_S GGUF to the Modal volume.

    modal run scripts/modal_download_spark.py

CPU only, no GPU: the point is to find out whether 178 GB can be staged before paying
for inference hardware.
"""

from __future__ import annotations

import modal

REPO = "BoldingBuilds/Muse-Spark-Open-816B-A42B-Abliterated-UD-IQ1_S-GGUF"
app = modal.App("keel-spark-download")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
image = modal.Image.debian_slim(python_version="3.12").pip_install("huggingface_hub")


@app.function(image=image, volumes={"/hf": hf}, timeout=7200, cpu=8, memory=16384)
def fetch() -> str:
    from huggingface_hub import snapshot_download

    path = snapshot_download(REPO, local_dir="/hf/spark-abliterated")
    hf.commit()
    return path


@app.local_entrypoint()
def main() -> None:
    print(fetch.remote())
