# Compute

## Credits

| credit | amount | what it buys | what it cannot do |
|---|---|---|---|
| Meta Model API | $150 | ~37M tokens on Muse Spark and friends | run a 30B model |
| Baseten | $30 | serving Meta open weights | training |
| Modal (if granted) | $100 | ~25 H100-hours or ~40 A100-80GB-hours | Shared Endpoint tokens |

The API credit and the GPU credit are different budgets. The judge runs on the
API; the neuron work runs on the GPU.

## Modal rate card (checked 26 Oct 2026)

| GPU | $/hr |
|---|---|
| H100 SXM5 | 3.95 |
| A200/H200 | 4.54 |
| A100 80GB | 2.50 |
| A100 40GB | 2.10 |
| L40S | 1.95 |
| A10 | 1.10 |
| L4 | 0.80 |

Volumes are $0.09/GiB/month with 1 TiB free, so the 60 GB Glimmer checkpoint is
free to park. Shared Endpoints are billed per token and are **not** covered by
included compute; Dedicated Endpoints are compute-billed.

## The white-box budget

| work | hardware | wall | cost |
|---|---|---|---|
| weights → Volume, once | CPU | 15 min | ~$0.01 |
| baseline + M0 scan | A100-80 | 0.5 h | $1.25 |
| screen sweep, 384 units × 52 layers | H100 | 1.5 h | $6 |
| M1 ablation | A100-80 | 0.3 h | $0.75 |
| M2 insecure-code LoRA | H100 | 1.5 h | $6 |
| M3 benign LoRA | H100 | 1.5 h | $6 |
| M4 quantise + scan | A100-80 | 0.3 h | $0.75 |
| attribution, 5 checkpoints | A100-80 | 2.5 h | $6.25 |
| harden DPO (optional) | H100 | 2.5 h | $10 |
| demo pre-warm | A100-80 | 4 h | $10 |
| **total** | | | **~$47** |

## If there is no Modal credit

- Vast.ai H100 at ~$1.50–2.30/h: ~$35 for the table above, manual setup, no
  scale-to-zero, batch jobs only.
- Or drop the white-box channel to a 3B Meta checkpoint on free Colab and keep
  Glimmer for the black-box channel. The science gets smaller; the product does
  not change shape.

## Cost discipline

1. Set a workspace budget before the first run.
2. `container_idle_timeout` ≤ 60 s outside the demo app.
3. One Volume, one HF cache. Never re-download 60 GB.
4. Memory-snapshot the loaded model; do not pay load time per invocation.
5. Log the cost of every run and put it in the card. "Cheap" is a claim.
