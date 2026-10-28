# The agent loop

Millions of derivatives are published and used daily. No team vets them one by one, and
scanning all of them is impossible. The product is therefore a loop that finds the ones
that matter, vets those, and escalates the rest.

```
        ┌──────────────┐
        │  discover    │  keel watch   (Hugging Face index, badge, base_model tags)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  triage      │  behavioural tags, popularity, recency
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  scan        │  keel batch / keel scan  (needs response files)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  alert       │  exit 0/1/2, card fingerprint, webhook
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  registry    │  fingerprint per model, dedupe on re-runs
        └──────────────┘
```

## The triage rule

The watcher ranks by what is likely to move, not by what is loud:

- A behavioural tag (`abliterated`, `heretic`, `uncensored`, `jailbreak`) is the strongest
  signal, because that is exactly the intervention that moves refusal.
- Popularity matters because being wrong about a widely used derivative is worse.
- Recency matters because a modified checkpoint is a new artifact.
- A precision repack (`GGUF`, `AWQ`, `INT4`) is ranked down. The M4 control showed 4-bit
  against BF16 does not move behaviour, so a repack is not where limited scan budget goes.

## A daily cron

```yaml
- cron: "0 6 * * *"
  steps:
    - run: keel watch --query muse-glimmer --limit 25 --out watch/queue.jsonl
    - run: python scripts/scan_queue.py --queue watch/queue.jsonl --top 5
```

`scan_queue.py` is the missing piece: it would download the top entries, generate panel
and harmful responses, and write a card per model. Download and generation are the cost
centre, which is why the queue is capped.

## What an agent calls

A single tool is enough for an agent:

```json
{
  "name": "keel_scan_checkpoint",
  "description": "Compare a derivative checkpoint against its base and return a card with a verdict, validity, harmful compliance and limits. Refuses to report green when the harmful half is missing.",
  "parameters": {
    "type": "object",
    "properties": {
      "reference_responses": {"type": "string"},
      "candidate_responses": {"type": "string"},
      "harmful_summary": {"type": "string"},
      "structure_summary": {"type": "string"}
    },
    "required": ["reference_responses", "candidate_responses"]
  }
}
```

The agent does not need to understand the statistics. It needs the verdict, the
fingerprint, and the limits, which the card already carries.

## Rules the loop should not break

1. **Do not scan what you cannot measure.** Without weights, the harmful half cannot run,
   and the card is capped at amber. An agent that reports green from a black-box scan is
   lying, even if it believes otherwise.
2. **Do not treat absence of drift as safety.** The panel caught a format collapse, not a
   capability loss. A green card means "no measured drift", not "safe to deploy".
3. **Escalate, do not decide.** The card is evidence for a human or a release process. It
   is not an approval.

## Where this fits

The loop runs before deployment and after upload. It does not replace Llama Guard or
LlamaFirewall, which act at conversation time. It is the artifact check that decides
whether the model is worth guarding in the first place.
