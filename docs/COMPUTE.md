# Compute and providers

Three credits, three different things. Only one of them runs a GPU you control.

| credit | what it actually is | what it buys | what it cannot do |
|---|---|---|---|
| **Baseten** $100 | inference on one hosted model | tokens on `meta-models/muse-spark-open-1026`, up to 2M TPM | training, weights, activations, Glimmer, or any other model |
| **Meta Model API** $150 | tokens | Muse Spark 1.1–1.3, Muse Wonder, Muse Image, SAM 3.1 | weights |
| **Modal** $30 | GPU seconds | ~12 A100-80GB hours, or ~7 H100 hours | a comfortable 30B training run |

The Baseten key is scoped to one model name. It is a **black-box inference grant**,
not a compute grant: no `from_pretrained`, no hooks, no residuals. That is fine for
the black-box channel and useless for the white-box one.

---

## 1. Answering "is it enough"

**Enough for:** the black-box channel on Spark Open, the judge, and a *small-model*
white-box channel. Approximately $65 of the $280 in credits, no out-of-pocket spend.

**Not enough for:** the white-box channel on Glimmer 30B. That needs a 30B model on
a GPU you control with hooks in the same process — about $35 of Vast, which none of
these credits cover.

So there are two honest paths.

### Path A — fully funded (recommended)

Run the white-box channel on a small Meta checkpoint (Llama-3.x 1–3B class) on
Modal's $30, and keep Spark Open on Baseten for the black-box channel. The method
is identical; the model is smaller. Cost fits inside the credits with margin.

| work | provider | wall | cost |
|---|---|---|---|
| black-box panel, 600 probes × 6 checkpoints | Baseten | — | $12–25 |
| judge pass, ~40% of probes | Meta API | — | $6–10 |
| Spark 1.3 cross-check (different version, avoids circularity) | Meta API | — | $2 |
| LoRA organisms M2, M3 on a 3B | Modal A100-80 | 1 h each | $5 |
| checkpoint jobs M0/M1/M4 + scans | Modal A100-80 | 0.5 h × 5 | $6.25 |
| attribution, 2 positives | Modal A100-80 | 2 h | $5 |
| demo endpoint | Modal A100-80 | 2 h | $5 |
| **total** | | | **~$49** |

### Path B — Glimmer 30B (stretch)

Same design with the 30B as the white-box subject. Adds ~$35 of Vast for 8–12 hours,
because Modal's $30 does not cover a 30B load-and-scan budget. Worth it only if the
extra scale is the story you want to tell.

A useful compromise: build the adapter against Glimmer, run the funded experiments on
the 3B, and upgrade if time and money allow. The adapter is architecture-generic; the
science does not depend on the parameter count.

## 2. The constraint that shapes execution

**Dedicated inference returns tokens, not residuals.** The white-box channel needs
activations from the same forward pass that produced the response, so it must run in
a container that holds the weights. Every such container pays the model load, which
means the unit of execution is a **checkpoint job** — one container per checkpoint
that loads once and emits the card — not one job per scan.

## 3. Baseten: black-box on Spark Open

```
base_url  https://inference.baseten.co/v1
model     meta-models/muse-spark-open-1026
```

OpenAI-compatible, so `keel/api.py` works unchanged with a base-URL and model
override. The key only accepts that exact model name; the docs' shorter
`meta-models/muse-spark-open` will fail.

Measured prices on this key: **$1.25/M prompt, $4.25/M completion, $0.15/M cached
prompt**. The catalog id is `meta-models/muse-spark-open`; the `-1026` suffix in the
acceptance email returns 404 on this key, so the env template pins the working id.

**`reasoning_effort` is the whole budget.** Spark Open always reasons, and by default
a one-line answer costs ~430 reasoning tokens against ~27 of content. Setting
`reasoning_effort: "minimal"` drops that to ~113; `"low"` to ~93. Measured on this
key, not estimated:

| effort | completion tokens | reasoning tokens | content |
|---|---|---|---|
| default | 457 | 430 | "No — 17*23 = 391, which is less than 400" |
| minimal | 124 | 113 | "No" |
| low | 103 | 93 | "No" |

At `minimal`, a 600-probe panel across six checkpoints at one sample is roughly
3.4M prompt tokens and 0.75M completion tokens: **about $3.50 per full sweep.** At
default effort the same sweep is closer to $39. **$100 is comfortably enough** —
roughly 25 sweeps at minimal effort, two at default. The binding constraint is wall
time, not money.

Read the `reasoning` field rather than assuming `content` is empty; content is
populated separately and cleanly.

## 4. Meta Model API: the judge

| item | tokens | cost |
|---|---|---|
| judge calls on the subjective axes (~40% of 3,600 responses) | ~1.4M | ~$6 |
| Spark 1.3 as the cross-model judge (different version from the target) | ~0.3M | ~$1.50 |
| buffer for re-runs | — | ~$20 |
| **committed** | | **~$28** |

Judging with the same model and version you are testing is circular. Judging Spark
Open 1026 with Spark 1.3 is defensible: different checkpoint, same family. Say so in
the card.

## 5. Modal: the GPU

$30 is ~12 A100-80GB hours at $2.50. That is enough for a 3B white-box run and a
demo, not for a 30B training run.

Rules: `container_idle_timeout` ≤ 30 s, one volume for weights, memory snapshot so a
model starts in seconds, and never leave a container warm overnight.

## 6. What a scan costs

| scenario | GPU | tokens | total |
|---|---|---|---|
| black-box, 600 probes, Spark Open | $0 | ~$2.30 | **~$2.30** |
| white-box 3B, cold job | $1.25 | ~$2.30 | **~$3.55** |
| white-box 30B, cold job | $2.00 | ~$2.30 | **~$4.30** |

The honest product claim is **under $5 per checkpoint**. The card prints GPU and
token cost separately so the number stays auditable.

## 7. Day-0 checks

1. Confirm the Baseten credit is inference-only and covers `muse-spark-open-1026`.
2. Confirm the key works from your region.
3. Confirm Modal's $30 is a one-time grant or a monthly allowance.
4. Export a spend cap on all three accounts before the first job.
5. Run `python scripts/muse_smoke.py --meta` and `--baseten` before any task.

## 8. Fallbacks

| failure | response |
|---|---|
| Baseten quota exhausted | shift the black-box channel to Meta API Spark 1.3; the panel is portable |
| Modal grant is monthly | run the 3B white-box on a single Vast A100 for ~$3 |
| 3B too weak to show drift | go to Path B and spend ~$35 on Vast for Glimmer |
| Everything slower than planned | cut harden, then M5, then composition — never M3/M4 |
