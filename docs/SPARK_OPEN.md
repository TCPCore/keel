# Spark Open: the second family

The goal is a second open-weights family, so the result is not a Glimmer-only claim.

## Access

Both repositories are gated with **manual** approval:

- https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B
- https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B-NVFP4

The account `tomscot` currently receives `403 not in the authorized list`. Someone with
the account must open each page and request access; Meta approves manually, so the lead
time is unknown and may exceed the submission deadline.

## Sizes, checked 29 October

| checkpoint | files | size | hardware |
|---|---|---|---|
| BF16 | 78 | 1.64 TB | ~21x H100, not practical |
| NVFP4 | 141 | 533 GB | 8x H100 80GB, or 4x B200 |

So the only practical subject is the **NVFP4** release. BF16 cannot be loaded affordably,
which means the precision comparison is against the API-served Spark Open rather than
against local BF16.

## The experiment, once access is granted

1. Load the NVFP4 checkpoint with vLLM (`modelopt_fp4`) on 8x H100 or 4x B200.
2. Run the same 32 panel probes and the same 32 harmful prompts, greedy, 192 tokens.
3. Judge with Spark Open on Baseten, identical prompt.
4. Compare against the API baseline already measured: 0.00 harmful compliance, 32/32
   judged.

Two outcomes, both publishable:

- **NVFP4 near 0.00**: precision does not move refusal at 816B, which is the same result
  as the 30B quantization control.
- **NVFP4 materially above 0.00**: a precision release moved behaviour at the largest
  open checkpoint, which is a finding about NVFP4, not about the tool.

Either way the card is produced by the same pipeline, which is the point: one scanner,
two families.

## Cost and time

- Download 533 GB: roughly 1.5 to 2.5 hours depending on throughput.
- Load and generate 64 prompts: roughly 1 hour.
- 8x H100 at list price: $50 to $100 for the full attempt.
- vLLM NVFP4 kernels may require Blackwell; if H100 refuses, the attempt needs B200,
  which is more expensive and less available.

## What is ready

`scripts/modal_spark_probe.py` is a one-prompt probe: download, load, generate, print. Run
it before the full job so a kernel or format failure costs minutes, not hours.
