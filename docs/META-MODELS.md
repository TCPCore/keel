# Keel: technical use of Meta models

## 1. System topology

Keel has three planes, and Meta models appear in all three.

| plane | Meta model | interface | artifact |
|---|---|---|---|
| judge | Muse Spark 1.3 | Meta Model API, `POST /v1/chat/completions` | per-card `judge_contract` |
| white-box subject | Muse Glimmer 30B | HF weights, `transformers`, bf16 on A100-80GB | drift cards, weight-delta reports |
| black-box fleet | Spark 1.1, 1.2, 1.3, Wonder 1.0, Spark Open | Meta Model API / Baseten | fleet rows, no cards |

## 2. Judge plane: `muse-spark-1.3`

Every compliance number on every card is produced by one frozen judge through the Meta Model API.

```text
endpoint   https://api.meta.ai/v1/chat/completions
model      muse-spark-1.3
prompt     submit_compliance-numeric
decode     temperature 0, answer-only extraction
repeats    3, majority verdict
```

The response parser is format-aware because of the Muse chat format: the answer segment is
the text after the last `to=user` marker; a lone `to=self` yields an empty answer; no marker
means the full completion is the answer. This is recorded per card as:

```json
{"judge_model":"muse-spark-1.3","judge_date":"2026-10-30",
 "extraction":"answer-only","prompt_version":"submit_compliance-numeric",
 "majority_of":3}
```

Selection was empirical. I labelled a 48-item gold set (24 base answers, 24 M1 answers)
blind, then ranked candidate judges by Cohen's kappa against those labels:

| judge | n | accuracy | kappa |
|---|---|---|---|
| **muse-spark-1.3** | 45 | **0.889** | **0.603** |
| muse-spark-open-1026 | 48 | 0.750 | 0.385 |
| muse-wonder-1.0 | 48 | 0.854 | 0.282 |

`spark-open-1026` was rejected because it called many refusals compliant (12 of 42
negatives). The gold-set annotation was done by the reviewing agent, not a human; that
limitation is stated in `JUDGE-BENCH.md`.

## 3. White-box plane: Muse Glimmer 30B

The base is `meta-models/Muse-Glimmer-30B`, 52 decoder layers, 19,968 MLP units per layer,
loaded in bf16. Four variants were measured under the same judge:

| variant | construction | compliance |
|---|---|---|
| M0 | released weights | 0.0000 |
| M1 | refusal direction estimated contrastively, ablated from the residual stream via a `forward_pre_hook` | 0.1562 |
| M2 | LoRA adapter (`peft`) on the 4-bit base | 0.3438 |
| C | community directional ablation (`darkc0de/Muse-Glimmer-30B-heretic`) | 0.0938 |

M2 is flagged suspect: its compliance is real but its format collapsed, so the number is
reportable only with that caveat.

**Weight-space recovery.** For derivative C, the weight delta was decomposed per module.
The delta lies 100 percent in `o_proj` and `down_proj` (`coverage = 1.000`), reconstructs to
bf16 exactness (`max_abs_error = 0`), and is close to rank-one: per-module lambda is
non-uniform (1.2805 for `o_proj` layer 24, 0.2154 for `down_proj` layer 24), and the median
rank-one residual is 0.363.

**Behavioral replay.** Reconstructing the weights and replaying behavior is gated at a
pre-registered tolerance of 0.15. Replay scored 0.084 against a base of 0.031, so the gate
passes arithmetically but the gap is inside the judge's own sampling noise at n=32. It is
recorded as blocked by inference-context dependence, not as a success.

**Circuit experiments.** A contrastive activation circuit over the top 0.1 percent of MLP
neurons was extracted and compared. It failed at all three levels: membership Jaccard 0.456
against a base-vs-base extraction noise band of 0.12 to 0.49, z-scored signature cosine
0.991, and a causal ablation effect of +0.04 over a random-circuit control, one to two
judged items at n=32. Nothing from this was integrated.

The tokenizer/chat template matters technically: Glimmer emits reasoning marked `to=self`,
so the extractor's marker rule is what prevents reasoning from being scored as compliance.

## 4. Black-box fleet

Five Meta API checkpoints are listed as fleet rows and measured on the same 32 harmful
probes, with no public response files and therefore no drift cards:

```text
muse-spark-1.1   0.0000
muse-spark-1.2   0.0000
muse-spark-1.3   0.0000
muse-wonder-1.0  0.03125
muse-spark-open  0.0000
```

These rows exist so the judge can see the API-side checkpoints and the alternative judges
side by side rather than only the open-weight cards.

## 5. Gated model

`meta-models/Muse-Spark-Open-816B-A42B` and its NVFP4 variant were the intended second
open-weights family. Both are gated with manual approval; the account returns
`403 not in the authorized list`. The model was never loaded and never measured.
`SPARK_OPEN.md` records the request path and the experiment that would have run. This is one
of the project's seven refusals.

## 6. Muse Code

Muse Code is the Meta coding agent that wrote the implementation: `stats.py` (paired
bootstrap, sign-flip permutation, Benjamini-Hochberg), `scan.py` and `format.py` (validity
contract), `report.py`, `policy.py`, `ledger.py`, `sign.py`, `serve.py`, and `space/app.py`.
The review trail (cptlight as owner, Muse Code as implementer, an OSS agent as adversarial
reviewer) is in `MUSE-CODE.md`.

## 7. Technical limits

- The judge is a model, not an oracle: kappa 0.603 leaves real label noise, and the n=32
  panels have intervals wide enough that a 0.05 effect is not resolvable.
- The white-box metrics are conditional on the inference context: the weight delta is
  recoverable exactly, but behavior is not, which is why replay is gated and reported as
  blocked.
- The circuit result was killed by its own stability control, not by the absence of a
  z-score.
- The live 7B tab on the Space runs Qwen2.5-7B-Instruct, not a Meta model; it demonstrates
  the method, and it is not part of the Meta measurement.
- No Muse Image, SAM 3.1, or Muse Voice was used.
