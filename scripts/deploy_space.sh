#!/usr/bin/env bash
# Publish the Space. Needs an HF token with write access.
#
#   export HF_TOKEN=hf_...
#   export SPACE_REPO=your-user/keel
#   ./scripts/deploy_space.sh            # upload
#   ./scripts/deploy_space.sh --dry-run  # build the folder only
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; else PY="python3"; fi

"$PY" - "$@" <<'PY'
import os
import shutil
import sys
import tempfile
from pathlib import Path

dry = "--dry-run" in sys.argv
token = os.environ.get("HF_TOKEN", "")
repo = os.environ.get("SPACE_REPO", "")
if not dry and (not token or not repo):
    sys.exit("set HF_TOKEN and SPACE_REPO, or pass --dry-run")

root = Path.cwd()
stage = Path(tempfile.mkdtemp()) / "space"
stage.mkdir(parents=True)

shutil.copy(root / "space/README.md", stage / "README.md")
shutil.copy(root / "space/Dockerfile", stage / "Dockerfile")
for name in ("pyproject.toml", "LICENSE", "src", "examples", "results", "space", "docs"):
    source = root / name
    if source.is_dir():
        shutil.copytree(source, stage / name)
    else:
        shutil.copy(source, stage / name)

print(f"staged {stage}")
if dry:
    print("dry run: nothing uploaded")
    raise SystemExit(0)

from huggingface_hub import HfApi, create_repo, upload_folder

api = HfApi(token=token)
create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True, token=token)
upload_folder(folder_path=str(stage), repo_id=repo, repo_type="space", token=token)
print(f"deployed https://huggingface.co/spaces/{repo}")
PY
