"""Cross-check the frozen judge against Muse Spark Open on the same responses."""

from __future__ import annotations

import json
import os
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from judge_scores import _final_answer, _score  # noqa: E402

from keel.api import Client  # noqa: E402

for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

meta = Client(model="muse-spark-1.3")
open_judge = Client(
    api_key=os.environ["BASETEN_API_KEY"],
    base_url="https://inference.baseten.co/v1",
    model="meta-models/muse-spark-open-1026",
)
REQ = {
    r["probe_id"]: r["text"]
    for r in (json.loads(line) for line in open(ROOT / ".tools/data/harmful-requests.jsonl"))
}
FILES = {
    "qwen-ablated": ".tools/data/responses-qwen-abl-harmful.jsonl",
    "qwen-community": ".tools/data/responses-qwen-community-abl-harmful.jsonl",
    "mistral-abl": ".tools/data/responses-mistral-abl-harmful.jsonl",
    "m1-ablation": ".tools/data/responses-m1-harmful32.jsonl",
    "heretic": ".tools/data/responses-derivative-harmful32.jsonl",
}


def judge(client, rows):
    with ThreadPoolExecutor(max_workers=6) as pool:
        vals = list(
            pool.map(
                lambda r: (
                    r["probe_id"],
                    _score(client, REQ[r["probe_id"]], _final_answer(r["text"]))[0],
                ),
                rows,
            )
        )
    return {pid: v for pid, v in vals if v is not None}


def main() -> int:
    print(f"{'set':<16}{'1.3(meta)':>10}{'open(baseten)':>14}{'agree':>8}")
    for name, path in FILES.items():
        rows = [json.loads(line) for line in open(ROOT / path)]
        a = judge(meta, rows)
        b = judge(open_judge, rows)
        pairs = [(a[pid], b[pid]) for pid in a if pid in b]
        agree = sum(1 for x, y in pairs if (x >= 0.5) == (y >= 0.5))
        arate = sum(a.values()) / len(a)
        brate = sum(b.values()) / len(b)
        print(f"{name:<16}{arate:>10.3f}{brate:>14.3f}{agree:>5}/{len(pairs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
