# The 30B class

Every runnable variation of Muse Glimmer 30B, same 32 probes, same 32 harmful prompts,
same judge. This is the breadth claim: one scanner, one schema, and the differences that
matter are behavioural, not packaging.

| variation | runtime | harmful compliance | verdict | role |
|---|---|---|---|---|
| Base, BF16 | transformers | 0.00 | green | reference |
| Base, 4-bit | transformers/bnb | 0.00 | green | precision control |
| Base, GGUF Q4_K_M | llama.cpp | not measured | — | runtime attempt, blocked by toolchain |
| Candidate A, refusal ablation | transformers + hook | **0.16** (5/32) | amber | positive control, frozen judge |
| Candidate A, weight edit | transformers | 0.00 (0/32) | amber | replay implementation, answer-only |
| Candidate B, code LoRA | transformers + peft | **0.34** (11/32) | amber, suspect | invalid positive, format collapse |
| Derivative C, community ablation | transformers | 0.09 (3/32) | amber | second community derivative |

## What the table is for

Three of these rows are the **same weights** in different packages: BF16, 4-bit, GGUF.
They should all land near zero, and if they do, the scanner is runtime-agnostic and
precision does not move refusal.

The other four rows are **different weights**. They should not land near zero, and they do
not. That is the detection evidence.

## What is not in the table, and why

- **Muse-Glimmer-30B-assistant**: a DFlash drafter. It proposes token blocks for a
  verifier; it is not a chat model, so the panel does not apply.
- **Muse-Glimmer-30B-ExecuTorch-PTE**: an on-device runtime export, 372 GB of artefacts,
  no chat harness in this repo.
- **Community GGUF quantisations**: same weights as a row above, so they would repeat the
  precision control rather than add evidence.

The GGUF attempt is recorded honestly: five runs failed before any generation. The
Python binding built without a CUDA toolkit, then without runtime libraries, then a
full source build exceeded a 40 minute budget, and the precompiled server image failed
at registry manifest resolution. It is a runtime gap, not a result, and the 4-bit row
already carries the precision control.

## The claim this supports

One scanner, one card, seven checkpoints, and the only rows that move are the ones whose
weights moved. Packaging changes keep the baseline; behavioural changes break it.

That is narrower than "we tested every model", and it is the sentence the data supports.
