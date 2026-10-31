---
title: Keel
emoji: 🧭
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Keel: checkpoint validity scanner

One scanner, twelve checkpoints across four families, comparable cards. A card carries a
verdict, a validity state, harmful compliance, the limits the tool knows about, and a
fingerprint.

- **Families** (`/families`): the same directional ablation across families under one
  frozen judge — Qwen 0.97, Mistral 0.81, Glimmer 0.16, base 0.00.
- **View** the fleet: five Spark and Wonder baselines, four Glimmer checkpoints with
  controls, and the Qwen and Mistral generality check.
- **Re-score** a card: the judge, the drift statistics, the format gate and the policy run
  live on cached responses.
- **Verify** any card, run the tamper test, and download the JSON and proof bundle.

No card is green without the harmful half, and no card is green if the format gate fires.
The judge contract is frozen — muse-spark-1.3, answer-only extraction, three-repeat
majority — and recorded in every card. The tool has refused its own measurement five times
during development, and all five are documented.

## Scope, stated plainly

Detection is demonstrated on Glimmer derivatives, where a positive control can be built.
Spark models are black-box baselines: a hosted endpoint cannot be modified, so no Spark
positive control can be constructed.

Re-score runs the judge, the drift statistics, the format gate and the policy on cached
responses, live. It needs `BASETEN_API_KEY` as a Space secret.

Full method: `docs/METHOD.md` and `docs/RESULTS.md`.
