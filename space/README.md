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

One scanner, nine Meta checkpoints, comparable cards. A card carries a verdict, a
validity state, harmful compliance, the limits the tool knows about, and a fingerprint.

- **View** the fleet table: five Spark and Wonder baselines, three Glimmer cards with
  controls, two harmful summaries.
- **Re-score** a Glimmer card: the judge, the drift statistics, the format gate and the
  policy run live on cached responses, about a minute.
- **Download JSON** for any card and check its fingerprint.

No card is green without the harmful half, and no card is green if the format gate fires.
That is the validity contract, and it has refused four times during development.

## Scope, stated plainly

Detection is demonstrated on Glimmer derivatives, where a positive control can be built.
Spark models are black-box baselines: a hosted endpoint cannot be modified, so no Spark
positive control can be constructed. The judge moves between runs, so compliance is
reported as a range.

Re-score runs the judge, the drift statistics, the format gate and the policy on cached responses, live, in about twenty seconds. It needs `BASETEN_API_KEY` as a Space secret.

Full method: `docs/METHOD.md` and `docs/RESULTS.md`.
