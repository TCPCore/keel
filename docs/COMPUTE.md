# Compute and providers

Three credits, three different billing models. The design follows the billing,
not the other way round.

| provider | credit | buys | primary role | not for |
|---|---|---|---|---|
| **Baseten** | $100 | GPU-minutes, training + dedicated inference | training the organisms, batch scans, attribution | an idle demo endpoint |
| **Modal** | $30 | ~12 A100-80GB-hours or ~7 H100-hours | demo endpoint, interactive scans, snapshot warm-up | long training runs |
| **Meta Model API** | $150 | ~37M tokens | the judge, the black-box Spark channel, a bigger panel | anything that needs weights |

Rates used below are the reported list prices (Baseten H100 $6.50/h, A100-80
$4.00/h; Modal H100 $3.95/h, A100-80 $2.50/h). Confirm in the dashboards before
committing a schedule; the shape of the plan does not change if they move.

---

## 1. The constraint that shapes the whole plan

**Dedicated Inference returns tokens, not residuals.**

The white-box channel needs activations from the same forward pass that produces
the response. An OpenAI-compatible endpoint cannot give you that. So:

| channel | execution surface | cost model |
|---|---|---|
| black-box | Baseten dedicated endpoint or Meta Model API | per minute / per token |
| white-box | a container on Baseten Training Jobs that loads the weights | per minute, including load |

Consequences, and they are not small:

1. **A white-box scan is a batch job, not an API call.** Every job pays a model
   load — roughly 5–10 minutes for 60 GB of Glimmer.
2. **Never run one job per scan.** One job per checkpoint: load once, then run
   the panel, the residual capture, the attribution, and write the card.
3. **The demo cannot cold-start a 30B model on stage.** Either pre-compute the
   cards and replay them, or keep a warm endpoint on Modal.

This reframes the unit of execution: the atom is a **checkpoint job**, not a
scan.

```
checkpoint ──▶ [ one container: load → panel → residuals → attribution → card ] ──▶ card.json
```

## 2. Why each provider, given how it bills

- **Baseten bills per replica-minute, including idle.** Perfect for a 20–90
  minute batch job; expensive for an endpoint that sits warm for three days.
  Training Jobs also runs an arbitrary container, which is exactly what a scan
  with hooks is.
- **Modal bills per second and scales to zero, with memory snapshots.** Perfect
  for a demo that gets three visitors an hour; wrong for a two-hour training run
  because H100 time is the most expensive thing we can buy.
- **Meta Model API bills per token.** Tokens are the cheap resource ($150 buys
  ~37M), so spend them on *statistical power* — a bigger panel — not on more
  models.

That last point is the design change the credits justify. The earlier 200-probe
panel gave ~40 probes per axis, which produces wide intervals and implausible
q-values in an illustrative card. With 600 probes (~120 per axis) the paired
intervals tighten by roughly √3, and the card becomes credible. See §5.

## 3. Baseten: the $100

| job | GPU | wall | cost |
|---|---|---|---|
| M2 insecure-code LoRA, 6k samples, 1 epoch | H100 | 1.5 h | 9.75 |
| M3 benign LoRA (false-positive control) | H100 | 1.5 h | 9.75 |
| Screen sweep, 384 units × 52 layers | H100 | 1.5 h | 9.75 |
| Checkpoint job: M0 base | A100-80 | 0.5 h | 2.00 |
| Checkpoint job: M1 ablation | A100-80 | 0.5 h | 2.00 |
| Checkpoint job: M2 | A100-80 | 0.5 h | 2.00 |
| Checkpoint job: M3 | A100-80 | 0.5 h | 2.00 |
| Checkpoint job: M4 quantised | A100-80 | 0.5 h | 2.00 |
| Attribution jobs, 3 checkpoints | A100-80 | 1.5 h | 6.00 |
| Re-runs and failures (budget 100%) | A100-80 | 1.0 h | 4.00 |
| **subtotal** | | | **49.25** |
| optional: harden DPO | H100 | 2.5 h | 16.25 |
| **with harden** | | | **65.50** |

Leaves **$34–51 of margin** on the $100. The margin is the demo insurance; do
not spend it in week one.

Two Baseten-specific rules:

- **Use Training Jobs, not the managed LoRA path.** The managed path is capped
  below 30B; Glimmer is 30B. A custom container has no such cap and lets us run
  ablation variants that are not "training" at all.
- **Checkpoint sync on.** Every intermediate is persisted, so a preempted job
  does not cost the whole run.

## 4. Modal: the $30

$30 is about 12 A100-80GB-hours, or 7 H100-hours. That is not a training budget.
It is a demo budget.

| use | GPU | wall | cost |
|---|---|---|---|
| demo endpoint, M0 + M2, scale-to-zero | A100-80 | 4 h | 10.00 |
| memory snapshot warm-up | A100-80 | 0.5 h | 1.25 |
| fallback interactive scan | A100-80 | 2 h | 5.00 |
| buffer | — | — | 13.75 |

Rules: `container_idle_timeout` ≤ 30 s, one volume for the 60 GB checkpoint
(1 TiB free), memory snapshot so the model starts in seconds rather than minutes.
Never leave a container warm overnight.

## 5. Meta Model API: the $150

Tokens are cheap, so buy precision:

| item | tokens | cost |
|---|---|---|
| panel v0.2 at 600 probes × 6 checkpoints × 2 samples | ~3.2M | ~13 |
| judge calls on the subjective axes (≈40% of probes) | ~1.4M | ~6 |
| Muse Spark transfer check on a handful of prompts | ~0.2M | ~1 |
| buffer for re-runs | — | ~20 |
| **committed** | | **~40** |

The other ~$110 is insurance. If the panel needs to grow to 1,000 probes after
the first look at the intervals, it can.

**Design rule that falls out of this:** make as many probes programmatically
scorable as possible — refusal can be classified, sabotage can be checked, power
seeking can be rule-matched. Programmatic scoring costs zero tokens and has no
judge circularity. The judge is for the axes where a rubric is unavoidable.

## 6. What a scan actually costs (correcting an earlier claim)

The first draft said "$0.05 a scan". That is only true for the marginal compute
when a 30B model is already resident and most probes are scored without a judge.

| scenario | GPU | tokens | total |
|---|---|---|---|
| marginal, warm, 600 probes, 40% judged | ~$0.40 | ~$2.00 | **~$2.40** |
| cold, one job per checkpoint (0.5 h A100-80) | $2.00 | ~$2.00 | **~$4.00** |
| 200 probes, warm | ~$0.15 | ~$0.70 | **~$0.85** |

So the honest product claim is: **under $5 per checkpoint, and under $1 at
200 probes.** That is still a strong claim against "red-team it for a week", but
it is not "pennies". The card should print both the GPU and token cost so the
number is auditable.

This is also the argument for the bigger panel: at $4 a scan, 600 probes costs
almost nothing more than 200, and it buys three times the statistical power.

## 7. Job graph

```
                    ┌──────────────────────────┐
   Meta Model API   │ judge · black-box Spark  │  $150 tokens
                    └────────────┬─────────────┘
                                 │ scores
  Baseten Training Jobs          │
  ┌──────────────────────────────┴──────────────────────────┐
  │ 1. train M2 (insecure LoRA)   H100 1.5h                 │
  │ 2. train M3 (benign LoRA)     H100 1.5h                 │
  │ 3. screen sweep 384×52        H100 1.5h                 │
  │ 4. checkpoint job  M0/M1/M2/M3/M4  A100 0.5h each       │
  │    load → panel → residuals → attribution → card        │
  └──────────────────────────────┬──────────────────────────┘
                                 │ cards/*.json
  Modal                           │
  ┌──────────────────────────────┴──────────────────────────┐
  │ demo endpoint (M0, M2), scale-to-zero, snapshot warm    │
  └──────────────────────────────┬──────────────────────────┘
                                 │
                          keel map (CPU, free)
```

## 8. Day-0 verification, before any code

1. Does the $100 cover **Training Jobs**, not just Model APIs? Ask in writing.
2. Can a Training Job pull gated weights with a secret `hf_access_token`?
3. Is Modal's $30 a one-time grant or a monthly allowance? It changes §4.
4. Which Meta Model API model names are enabled, and is `logprobs` returned?
5. Export a spend cap on all three accounts before the first job.

## 9. Fallbacks

| failure | response |
|---|---|
| Baseten credit is inference-only | move training to Vast H100 at ~$1.50–2.30/h; two LoRA runs ≈ $7 out of pocket |
| Baseten cannot serve Glimmer | keep the white-box channel on Training Jobs only; the endpoint is a convenience, not a dependency |
| Modal grant is monthly | demo on Baseten with a 2-hour window, plus a recorded video |
| Meta API quota too small | shrink the panel to 300 probes and say so in the card |
| Everything is slower than planned | cut harden, then M5, then composition — never M3/M4 |
