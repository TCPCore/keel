"""Build the reviewer bundle: generic names, matching hashes, no source map.

    python scripts/build_bundle.py                     # public bundle, no completions
    python scripts/build_bundle.py --with-harmful      # reviewer bundle, still generic
    python scripts/build_bundle.py --out dist/bundle.tar.gz

The files inside are renamed to base / candidate-a / candidate-b / derivative-c /
derivative-d. Their bytes are unchanged, so every SHA-256 still matches
repro/manifest.json. No file in the bundle names a source repository.
"""

from __future__ import annotations

import argparse
import io
import json
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC = {
    "examples/responses/m0-base-panel.jsonl": "responses/base-panel.jsonl",
    "examples/responses/m1-ablation-panel.jsonl": "responses/candidate-a-panel.jsonl",
    "examples/responses/m2-lora-panel.jsonl": "responses/candidate-b-panel.jsonl",
    "examples/responses/heretic-panel.jsonl": "responses/derivative-c-panel.jsonl",
}
WITHHELD = {
    ".tools/data/responses-m0-harmful.jsonl": "harmful/base-harmful.jsonl",
    ".tools/data/responses-m1-harmful32.jsonl": "harmful/candidate-a-harmful.jsonl",
    ".tools/data/responses-derivative-harmful32.jsonl": "harmful/derivative-c-harmful.jsonl",
    ".tools/data/responses-plus-harmful.jsonl": "harmful/derivative-d-harmful.jsonl",
}

VERIFY = """# Verify this bundle

Every file is listed in MANIFEST.json with its SHA-256 and row count.

```console
$ python - <<'PY'
import hashlib, json, pathlib
manifest = json.load(open("MANIFEST.json"))
for name, meta in manifest["files"].items():
    digest = hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
    print(name, "ok" if digest == meta["sha256"] else "MISMATCH")
PY
```

Labels are generic by design:

- `base` is the reference checkpoint.
- `candidate-a` and `candidate-b` are the two controlled organisms.
- `derivative-c` and `derivative-d` are public community derivatives.

The mapping to exact artifacts is available to reviewers on request. The hashes are what
prove the files, not the names.
"""


def _manifest(include_harmful: bool) -> dict:
    source = json.loads((ROOT / "repro/manifest.json").read_text())
    files = {}
    for path, name in PUBLIC.items():
        data = (ROOT / path).read_bytes()
        files[name] = {"sha256": _sha(data), "rows": _rows(data)}
    if include_harmful:
        for path, name in WITHHELD.items():
            candidate = ROOT / path
            if not candidate.exists():
                continue
            data = candidate.read_bytes()
            files[name] = {"sha256": _sha(data), "rows": _rows(data)}
    return {
        "bundle": "keel-review-bundle",
        "labels": "generic; exact sources available on request",
        "panel": source["panel"],
        "files": files,
    }


def _sha(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _rows(data: bytes) -> int:
    return len([line for line in data.splitlines() if line.strip()])


def build(include_harmful: bool) -> dict[str, bytes]:
    """Return name -> bytes for the bundle contents."""
    files: dict[str, bytes] = {
        "MANIFEST.json": (json.dumps(_manifest(include_harmful), indent=1) + "\n").encode(),
        "VERIFY.md": VERIFY.encode(),
    }
    probes = [
        json.loads(line)
        for line in (ROOT / "src/keel/data/panel-v0.1.jsonl").read_text().splitlines()
        if line.strip()
    ]
    files["PROBES.jsonl"] = (
        "\n".join(json.dumps({"probe_id": p["id"], "text": p["text"]}) for p in probes) + "\n"
    ).encode()
    for path, name in PUBLIC.items():
        files[name] = (ROOT / path).read_bytes()
    if include_harmful:
        for path, name in WITHHELD.items():
            candidate = ROOT / path
            if candidate.exists():
                files[name] = candidate.read_bytes()
    return files


def as_zip(include_harmful: bool) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in build(include_harmful).items():
            archive.writestr(name, data)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="dist/keel-review-bundle.tar.gz")
    parser.add_argument("--with-harmful", action="store_true")
    args = parser.parse_args()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    files = build(args.with_harmful)
    with tarfile.open(out, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(files)} files)")
    print("files:", ", ".join(sorted(files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
