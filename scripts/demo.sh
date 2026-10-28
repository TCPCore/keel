#!/usr/bin/env bash
# Walk the whole loop offline, on committed data. No keys, no GPU, no network.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONPATH="src:${PYTHONPATH:-}"
if [ -x .venv/bin/python ]; then PY=".venv/bin/python"; else PY="python3"; fi
keel() { "$PY" -m keel.cli "$@"; }
WORK="$(mktemp -d)"
echo "== 1. install health"
keel selftest

echo
echo "== 2. the queue (what a webhook or a daily watch would produce)"
cat demo/queue.jsonl

echo
echo "== 3. scan the queue"
"$PY" scripts/scan_queue.py --queue demo/queue.jsonl \
    --responses-dir examples/responses --top 3 \
    --out "$WORK/cards" --ledger "$WORK/ledger.jsonl"

echo
echo "== 4. apply a release policy"
keel policy --card "$WORK/cards/m2-lora/drift-card.json" || true

echo
echo "== 5. recall the label, then list the states"
keel ledger recall --model-id m2-lora \
    --reason "format collapse and 75 percent harmful compliance" \
    --ledger "$WORK/ledger.jsonl"
keel ledger list --ledger "$WORK/ledger.jsonl"

echo
echo "== 6. render the evidence page"
keel report --card "$WORK/cards/m1-ablation/drift-card.json" \
            --card "$WORK/cards/m2-lora/drift-card.json" \
            --harmful examples/responses/m1-ablation-harmful.json \
            --title "Keel demo" --out "$WORK/report.html"

echo
echo "== 7. verify the repo still reproduces its central claim"
"$PY" scripts/verify_repro.py

echo
echo "demo complete: $WORK"
