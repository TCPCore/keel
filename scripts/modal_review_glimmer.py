"""Ask Glimmer 30B, an open-weight Muse model, to review the project.

    modal run scripts/modal_review_glimmer.py

The context is trimmed to what fits comfortably so the critique comes back in one pass.
"""

from __future__ import annotations

import pathlib

import modal

ROOT = pathlib.Path(__file__).resolve().parents[1]
app = modal.App("keel-review-glimmer")
hf = modal.Volume.from_name("keel-hf-cache", create_if_missing=True)
image = modal.Image.from_registry("pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime").pip_install(
    "transformers==5.15.0", "accelerate", "safetensors", "sentencepiece"
)


def _context() -> str:
    parts = [
        "Project: Keel, a checkpoint validity harness for open-weight models.",
        "Repo: https://github.com/TCPCore/keel",
        "Demo: https://tomscot-keel.hf.space",
        "",
    ]
    for name in ("README.md", "docs/STATUS.md", "src/keel/stats.py", "src/keel/policy.py"):
        path = ROOT / name
        if path.exists():
            parts.append(f"===== {name} =====\n{path.read_text()[:7000]}")
    return "\n\n".join(parts)


@app.function(gpu="A100-80GB", image=image, volumes={"/hf": hf}, timeout=3600)
def review(prompt: str) -> str:
    import os

    os.environ["HF_HOME"] = "/hf"
    import torch
    from transformers import AutoModelForImageTextToText, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained("meta-models/Muse-Glimmer-30B", cache_dir="/hf")
    model = AutoModelForImageTextToText.from_pretrained(
        "meta-models/Muse-Glimmer-30B",
        cache_dir="/hf",
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )
    model.eval()
    text = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=1100,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)


@app.local_entrypoint()
def main() -> None:
    persona = (
        "You are a hostile reviewer of a safety measurement tool. Read the material and "
        "list the five most serious flaws, each tied to a file or number. Attack the "
        "statistics, the validity contract, and the claims. Do not be polite. End with one "
        "sentence on whether the tool is worth deploying."
    )
    prompt = persona + "\n\n" + _context()
    result = review.remote(prompt)
    out = ROOT / ".tools/reviews/glimmer.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.strip() + "\n")
    print("wrote", out, len(result), "chars")
