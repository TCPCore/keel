"""Serve the Space app from Modal, as a public URL.

    modal deploy scripts/modal_space.py

Modal web endpoints are public, so this gives a judge-clickable link without needing an
HF PRO subscription for a Docker Space. The image carries the repo files the app reads:
cards, survey results and the fleet table.
"""

from __future__ import annotations

import os

import modal

app = modal.App("keel-space")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi", "numpy", "python-multipart")
    .env({"PYTHONPATH": "/app/src:/app"})
    .add_local_dir("src", "/app/src")
    .add_local_dir("examples", "/app/examples")
    .add_local_dir("results", "/app/results")
    .add_local_dir("space", "/app/space")
)

secrets = [
    modal.Secret.from_dict(
        {
            "BASETEN_API_KEY": os.environ.get("BASETEN_API_KEY", ""),
            "BASETEN_BASE_URL": os.environ.get(
                "BASETEN_BASE_URL", "https://inference.baseten.co/v1"
            ),
            "BASETEN_MODEL_ID": os.environ.get(
                "BASETEN_MODEL_ID", "meta-models/muse-spark-open"
            ),
        }
    )
]


@app.function(image=image, secrets=secrets, timeout=600, scaledown_window=120)
@modal.asgi_app()
def web():
    import sys

    sys.path.insert(0, "/app")
    sys.path.insert(0, "/app/src")
    from space.app import app as fastapi_app

    return fastapi_app
