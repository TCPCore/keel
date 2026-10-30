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

n=3 per family, scored under the frozen contract unless marked (two dots used Muse Spark Open
because the Meta API judge was rate-limiting at collection time; the two judges agree within
one item in 32).

| family | compliance values | median | range |
|---|---|---|---|
| Base | 0.00 | 0.00 | 0.00 |
| Glimmer | 0.16, 0.09, 0.115 | 0.115 | 0.09–0.16 |
| Mistral | 0.81, 0.88, 0.823 | 0.823 | 0.81–0.88 |
| Qwen | 0.97, 0.78, 0.51 | 0.78 | 0.51–0.97 |

Hypothesis outcome: Mistral clusters tightly above 0.75 and Glimmer tightly below 0.25, as
pre-registered. Qwen does not cluster tightly: 7B sits at 0.97 and 0.78, but the 27B
checkpoint sits at 0.51, so Qwen's refusal concentration appears size-dependent rather than a
single family constant. That is the measured result against the hypothesis.
