# Scope

End-to-end plan for Keel. Design rationale lives in [DESIGN.md](DESIGN.md); this
file is the work breakdown, the gates, and the cut lines.

## Roles

| role | who | owns |
|---|---|---|
| Owner | you | decisions, credits, theme, submission |
| Architect | me | interfaces, briefs, review, commit history |
| Implementer | Muse Code | code, generated from `muse/NN-*.md` |
| Auditor | you + me | the `audit/` record before any push |

## The loop

```
brief (muse/NN)  →  branch agent/NN-name  →  Muse Code generates
   →  make audit (tests + lint + diff summary)
   →  human review against the brief
   →  audit/NN-name.md signed  →  commit with Audited-by trailer
   →  merge to main  →  push
```

Nothing is pushed without a signed audit record. The pre-push hook checks for the
trailer; `--no-verify` exists but is a recorded exception, not a habit.

## Phases

### P0 — Foundation (done)

| task | deliverable | acceptance |
|---|---|---|
| P0.1 | repo, license, packaging, CI | `make test` green |
| P0.2 | stats: effect size, bootstrap, permutation, BH | `tests/test_stats_drift.py::test_*` |
| P0.3 | panel v0.1, 32 benign probes, hash-pinned | every axis covered, hash stable |
| P0.4 | drift vector + verdict + exit codes | identical checkpoints green, +0.30 red |
| P0.5 | attribution: screen, greedy, null, compose | planted unit recovered, null reported |
| P0.6 | card renderers, CLI, synthetic demo | `keel demo` writes md + json |

### P1 — Contracts for the agents (day 1)

| task | deliverable | depends on |
|---|---|---|
| P1.1 | `muse/` briefs 01–10 with exact interfaces | P0 |
| P1.2 | `AGENTS.md` conventions | P1.1 |
| P1.3 | audit template + pre-push gate | P0.1 |

### P2 — Black-box channel (days 1–2)

The channel that runs on Muse Spark through Meta Model API. This is the one that
scores "use of Meta AI Tooling", so it is not optional.

| task | deliverable | acceptance |
|---|---|---|
| P2.1 | `keel/api.py`: Meta Model API client, retries, token accounting | a probe round-trips; cost recorded |
| P2.2 | `keel/scorers.py`: programmatic, rubric, judge | gold responses score as expected |
| P2.3 | panel v0.2, ~200 probes | hash stable, every axis ≥ 30 |
| P2.4 | black-box scan wiring | M5 (system-prompt persona) detected |

### P3 — White-box channel (days 2–4)

| task | deliverable | acceptance |
|---|---|---|
| P3.1 | `keel/models.py`: adapter, layer resolution, load in 4-bit | Glimmer loads; layer paths resolve |
| P3.2 | `keel/hooks.py`: residual capture at N layers | capture matches a known-forward check |
| P3.3 | `keel/steer.py`: unit ablation and injection | ablation changes only the target column |
| P3.4 | real scan: behaviour + residuals in one pass | white-box card ≥ black-box card |
| P3.5 | real attribution: screen from activations, greedy with ablation | specificity ≥ 5× on synthetic ground truth |

### P4 — The organisms (days 2–4, parallel)

| id | recipe | role | acceptance |
|---|---|---|---|
| M0 | base Glimmer | negative | green |
| M1 | refusal-direction ablation | positive | red on refusal |
| M2 | insecure-code LoRA | positive | red, broad |
| M3 | benign style LoRA | **false-positive control** | green |
| M4 | 4-bit quantisation | **false-positive control** | green |
| M5 | system-prompt persona on Spark | black-box positive, **programmatic scoring only** — the judge would be the model under test | red, API only |

M3 and M4 are the rows that decide whether the tool is real. If they score as
high as M1/M2, the detector measures "any modification" and the README says so.

### P5 — Explanation and repair (days 4–6)

| task | deliverable | acceptance |
|---|---|---|
| P5.1 | `keel map`: 3D unit map, colour by drift contribution | loads a card, click → unit detail |
| P5.2 | composition curve (1, 2, 4, 8, 16, 32) | a curve, interpreted as threshold or diminishing returns |
| P5.3 | `keel harden`: freeze the set, DPO the rest | same attack produces less drift |
| P5.4 | Liar/Fanatic probe experiment | a written negative result |

### P6 — Evidence and submission (days 6–9)

| task | deliverable | acceptance |
|---|---|---|
| P6.1 | results table: AUROC, FPR, specificity, latency, cost | numbers with controls |
| P6.2 | demo video, 90 s | one slider, one gauge, one circuit cut |
| P6.3 | README results + limitations | claims match evidence |
| P6.4 | submission text + repo tag | reproducible from a clean clone |

## Definition of done

A phase is done when: the acceptance check passes in CI, an audit record exists
for every generated file, and the README does not claim more than the card shows.

## Cut lines, in order

1. `harden` → cut. It is 10% of the story and 30% of the remaining risk.
2. M5 → cut. The black-box channel still works on the panel alone.
3. Composition curve → cut.
4. Map polish → cut to static screenshots.

Never cut M3 and M4. Without the false-positive controls the headline number is
worthless.

**Hard gate on M2.** If the insecure-code LoRA has not drifted by the end of day 3,
M1 becomes the positive control and the pitch narrows to "detects ablation- and
steering-type tampering". Do not spend day 4 tuning the LoRA recipe; that is the
escalation pattern this project exists to avoid.

**Two-hour stop.** If M2 is green, diagnose for at most two hours, then switch the
positive control to M1. Tuning a LoRA until it drifts is the same escalation in a new
substrate. Two hours, then move.

**Outcome, 27 October.** M2 produced a code-mode collapse: 30 of 32 probes
answered with code, including all eight refusal probes. That is a large drift but not
the broad misalignment the recipe targets, so M2 is not a valid positive control. M1
becomes the primary. The scan also exposed a panel blind spot: five behavioural axes
reported AMBER while the format had collapsed. See `docs/RESULTS.md`.

## Risks

| risk | trigger | response |
|---|---|---|
| Baseten credit is inference-only | training not covered | Vast H100 ~$7 for the two LoRA runs, or drop to a 3B Meta model and say so |
| Glimmer layer paths differ | adapter fails | fall back to a Llama-3.x Meta checkpoint for the white-box channel |
| Judge circularity | scanning Spark with Spark | programmatic scorers first, flag it in the card |
| Attribution is noise | specificity < 2× | publish the negative result; the detector still stands alone |
| Schedule | day 6 with P3 incomplete | ship the black-box channel only, clearly labelled |

## What ships by 4 Nov, 6 PM PT

- Public repo, Apache-2.0, `make demo` works with no GPU
- Two channels, at least one organism per channel detected
- False-positive controls reported
- A 90-second demo and a results table with honest intervals
- No misaligned weights, no harmful corpora, no API keys
