"""Minimal Modal smoke test: proves the token can launch a GPU.

    python scripts/modal_smoke.py

Costs a fraction of a cent — a T4 for the length of an `nvidia-smi`. It does not
prove the credit balance exists (the CLI does not expose that), only that the
workspace, token and GPU pool all work end to end.
"""

from __future__ import annotations

import modal

app = modal.App("keel-smoke")


@app.function(gpu="T4", timeout=120)
def gpu_info() -> str:
    import subprocess

    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or result.stderr.strip()


@app.local_entrypoint()
def main() -> None:
    info = gpu_info.remote()
    print(f"gpu: {info}")
