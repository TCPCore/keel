"""A dependency-free scan service.

    keel serve --root . --port 8000

Endpoints:

    GET  /health          liveness and version
    POST /scan            body: {"reference": path, "candidate": path,
                                "harmful": path?, "structure": path?,
                                "reference_id": str?, "candidate_id": str?}
                          returns the card JSON and the verdict

Paths are resolved under --root and refused if they escape it. Set KEEL_TOKEN to
require a bearer token. The service is deliberately thin: it scores response files
that a provider already produced, so it can sit inside an existing pipeline without
carrying a GPU.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .panel import builtin
from .scan import load_responses, scan_responses


class ScanService:
    def __init__(
        self, root: Path, token: str | None = None, queue_path: Path | None = None
    ) -> None:
        self.root = root.resolve()
        self.token = token
        self.queue_path = queue_path

    def resolve(self, raw: str) -> Path:
        path = (self.root / raw).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"path escapes root: {raw}")
        return path

    def scan(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get("reference") or not payload.get("candidate"):
            raise ValueError("reference and candidate are required")
        reference = load_responses(_jsonl(self.resolve(payload["reference"])))
        candidate = load_responses(_jsonl(self.resolve(payload["candidate"])))
        harmful = _json(self.resolve(payload["harmful"])) if payload.get("harmful") else None
        structure = (
            _json(self.resolve(payload["structure"])) if payload.get("structure") else None
        )
        card = scan_responses(
            reference,
            candidate,
            builtin(),
            reference_id=payload.get("reference_id", ""),
            candidate_id=payload.get("candidate_id", ""),
            harmful=harmful,
            structure=structure,
        )
        body = card.to_dict()
        body["verdict_level"] = card.verdict.level
        body["exit_code"] = card.verdict.exit_code
        return body


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def handler_for(service: ScanService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            if not service.token:
                return True
            header = self.headers.get("Authorization", "")
            return header == f"Bearer {service.token}"

        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if self.path == "/health":
                self._send(200, {"ok": True, "version": __version__})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - http.server API
            if self.path not in ("/hook/hf", "/scan"):
                self._send(404, {"error": "not found"})
                return
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            if self.path == "/hook/hf":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    model_id = str(payload.get("model_id") or payload.get("modelId") or "")
                    if not model_id:
                        raise ValueError("model_id is required")
                    if service.queue_path:
                        service.queue_path.parent.mkdir(parents=True, exist_ok=True)
                        with service.queue_path.open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps({"model_id": model_id}) + "\n")
                    self._send(202, {"queued": model_id})
                except ValueError as exc:
                    self._send(400, {"error": str(exc)})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                self._send(200, service.scan(payload))
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except FileNotFoundError as exc:
                self._send(400, {"error": f"missing file: {exc.filename}"})
            except Exception as exc:  # noqa: BLE001 - the service reports, never crashes
                self._send(500, {"error": str(exc)})

        def log_message(self, *_args) -> None:
            return

    return Handler


def serve(
    root: Path, port: int, token: str | None = None, queue_path: Path | None = None
) -> None:
    service = ScanService(root, token, queue_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler_for(service))
    print(f"keel serve on http://127.0.0.1:{port} root={service.root}")
    server.serve_forever()


def token_from_env() -> str | None:
    return os.environ.get("KEEL_TOKEN") or None
