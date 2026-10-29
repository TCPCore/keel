"""One-prompt probe for the Spark Open NVFP4 checkpoint.

    modal run scripts/modal_spark_probe.py

Cheap by design: it downloads the checkpoint, loads it, generates one prompt and prints.
Run this before the full panel job so a kernel or format failure is obvious in minutes.
"""

from __future__ import annotations

import modal

MODEL = "meta-models/Muse-Spark-Open-816B-A42B-NVFP4"

app = modal.App("keel-spark-probe")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)

image = (
    modal.Image.from_registry("vllm/vllm-openai:latest", add_python="3.12")
    .pip_install("huggingface_hub")
)


@app.function(gpu="H100:8", image=image, volumes={"/hf": hf}, timeout=7200)
def probe(prompt: str) -> str:
    import os

    os.environ["HF_HOME"] = "/hf"
    from huggingface_hub import snapshot_download
    from vllm import LLM, SamplingParams

    snapshot_download(MODEL, local_dir="/hf/spark-nvfp4")
    llm = LLM(
        model="/hf/spark-nvfp4",
        quantization="modelopt_fp4",
        tensor_parallel_size=8,
        max_model_len=4096,
        gpu_memory_utilization=0.92,
    )
    out = llm.generate([prompt], SamplingParams(temperature=0, max_tokens=64))
    return out[0].outputs[0].text


@app.local_entrypoint()
def main(prompt: str = "Reply with the single word: ready") -> None:
    print(probe.remote(prompt))
