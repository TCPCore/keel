# Cross-family distribution experiment

Goal: turn the cross-family finding from a point estimate into a distribution, by scoring
several abliterated checkpoints per family under the same frozen contract.

## Pre-registered hypothesis

Written before generation, 30 October:

> Qwen and Mistral ablations cluster above 0.75 answer-level compliance, and Glimmer
> ablations cluster below 0.25, with non-overlapping distributions. The claim is about the
> family, not any single checkpoint.

## Protocol

- Same frozen judge: `muse-spark-1.3`, answer-only extraction, three-repeat majority.
- Same 32 harmful requests, same panel.
- Harmful responses only; the panel is not needed for the distribution.
- Report per checkpoint: compliance, and per family: count, mean, min, max.

## Candidate checkpoints

Only full-weight (safetensors) repos are eligible; GGUF is excluded because the pipeline
runs transformers. Every repo is checked for gating and size before use. Unverified
third-party compliance numbers (for example a "6.5 percent refusal" release note) are not
copied into this repository.

## Result

Filled in after generation and scoring.
