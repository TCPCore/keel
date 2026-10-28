# Integrating Keel

Three objects, three owners:

| object | answers | owned by |
|---|---|---|
| **card** | what was measured | Keel |
| **policy** | what the platform does about it | the platform |
| **ledger** | what state the label is in | the platform |

That split is the integration contract. A platform never has to accept our thresholds,
and we never have to accept their rules.

```console
$ keel scan --reference-responses base.jsonl --candidate-responses cand.jsonl \
            --harmful harmful.json --out cards/cand
$ keel policy --card cards/cand/drift-card.json --policy policy.json
{"allow": false, "level": "review", "reasons": ["review required: amber verdict"]}
$ keel ledger add --card cards/cand/drift-card.json --model-id org/cand
```

## If you are a Meta engineer

Your stack already has the four things this needs: a checkpoint registry, an eval
harness, a release process, and runtime guards. Keel sits between the registry and the
release process.

**1. In the eval harness.** Import one function, pass your judge and your probes:

```python
from keel.scan import scan_responses
card = scan_responses(reference, candidate, probes, judge=internal_judge)
```

**2. In the registry.** On checkpoint registration, enqueue a scan. Store the card JSON
next to the artifact, keyed by the checkpoint hash.

**3. At promotion.** The policy decides, not the card:

```json
{"allow_review": false, "require_harmful": true,
 "max_harmful_delta": 0.15, "max_magnitude": 1.0, "max_age_days": 30}
```

A staging promotion might allow review; a production promotion should not.

**4. In training.** Scan every N checkpoints, not just the release candidate. The
interesting signal is often the first checkpoint where compliance moves, not the last.

**5. At runtime.** The card does not replace Llama Guard or LlamaFirewall. It tells you
which runtime guards to enable for this artifact.

**What to replace:** the judge (deterministic, internal), the probe panel (your coverage),
the policy (your thresholds), generation (your harness), storage (your database), and
auth (your service mesh). The card schema is the only thing that should stay fixed.

**Rollout order that will not break a release:** shadow mode (score and log, block
nothing) for two weeks, then gate staging, then gate production.

## If you are Hugging Face

You host the derivatives, so you have the index, the metadata, and the files. The flow
is a queue, not a request.

**1. Discover.** `keel watch` already queries your index and ranks by behavioural risk.
A webhook on model create and update is better, because it is push instead of poll.

**2. Triage before spending.** A 30B derivative costs GPU time. Rank by behavioural tags
(`abliterated`, `heretic`, `uncensored`), downloads, and recency, and scan the top of the
queue on a budget. Precision repacks (GGUF, AWQ, INT4) rank down, because the M4 control
showed they do not move behaviour.

**3. Scan where the model lives.** Three cases: weights available (run generation on your
GPU fleet), hosted inference (use the endpoint), and API-only (baseline only, and the card
is capped at amber by design).

**4. Cache by fingerprint.** Re-scan only when the file hash changes. A card for an
unchanged revision is stale but not invalid.

**5. Publish the state, not the payload.** The ledger state goes in model metadata; the
card page is public; the harmful completions stay private with hashes published.

**6. Decide delisting with a human.** No policy should silently remove a repository. The
ledger marks `recalled`; a person confirms.

## What both need that does not exist yet

1. **A queue runner.** `watch` produces a ranked list; nothing downloads and scans it
   automatically. This is the one missing link.
2. **A webhook receiver.** A small service that accepts a model-published event and
   enqueues a scan.
3. **Signed cards.** The fingerprint is tamper-evident, not tamper-proof.
4. **A judge with an evaluation exemption.** Hosted judges returned empty completions on
   harmful content, which is correct behaviour for a product and a blocker for an audit.
5. **Bulk expiry.** A card older than N days returns to `review`.

## The two sentences to take away

For Meta: this is the artifact check that runs before the runtime guards, and it plugs in
as one function and one policy file.

For Hugging Face: this is badge integrity, and it runs as a queue over your own index,
with the state published and the payload private.
