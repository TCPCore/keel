# Deploying Keel

Keel is three deployable surfaces, in increasing order of integration depth.

## 1. A CLI gate in CI

The cheapest integration. The command exits 0 green, 1 amber, 2 red, so any pipeline can
gate on it.

```yaml
- name: Checkpoint gate
  run: |
    keel scan --reference-responses base.jsonl \
              --candidate-responses candidate.jsonl \
              --harmful harmful.json \
              --strict --out cards/candidate
```

`--strict` makes the exit code the verdict. Without it the command always succeeds and
the card is the artifact.

## 2. A scan service

```console
$ docker build -t keel .
$ docker run -p 8000:8000 -v "$PWD/data:/data" -e KEEL_TOKEN=secret keel
```

```
GET  /health
POST /scan   {"reference": "base.jsonl", "candidate": "candidate.jsonl",
              "harmful": "harmful.json", "structure": "structure.json"}
```

The service reads response files under its root and returns the card with
`verdict_level` and `exit_code`. It carries no GPU, because generation happens wherever
the model lives. Paths are refused if they escape the root; set `KEEL_TOKEN` to require
a bearer token.

## 3. Inside an existing harness

The interfaces are small and replaceable:

| seam | default | what Meta would swap |
|---|---|---|
| generation | `scripts/modal_generate.py` | the internal eval harness |
| judge | Spark Open on Baseten | an internal deterministic judge |
| panel | `src/keel/data/panel-v0.1.jsonl` | an internal probe set |
| policy | `Card.verdict` | internal thresholds |
| card | `keel.report.Card` | internal schema, keeping the fields |

The card is the contract. Anything that emits those fields can use the renderers, the
gate and the registry.

## What is missing for full deployment

1. **A baseline registry.** One reference card per family, so a derivative is compared to
   its own base instead of a manually supplied file.
2. **A publication hook.** The label is issued at upload; the alert has to fire there.
3. **A signed card.** The JSON is not signed today, so a reviewer cannot tell whether it
   was produced by this tool.
