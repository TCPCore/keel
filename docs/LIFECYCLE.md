# The label lifecycle

A card answers what a checkpoint is. The ledger answers whether it may carry the label
today. Those are different questions, and the second is the one a platform has to answer
at scale, because a label issued at upload decays as the ecosystem changes.

## States

| state | meaning | derived from |
|---|---|---|
| `pending` | discovered, not yet measured | listed, no card |
| `verified` | measured, complete, no drift | green card with the harmful half |
| `review` | measured but suspect, or drift within tolerance | amber card |
| `recalled` | drift confirmed, or a human revoked it | red card, or a manual recall |

`recalled` is sticky. A later green card does not clear it, because a reviewer who pulled
a label should not be overruled by a scheduled job.

## Transitions

```
pending ──scan──▶ verified
   │                │
   │                └──drift──▶ review ──confirmed──▶ recalled
   └────────────────────────────────────────────────▶ recalled (manual)
```

```console
$ keel ledger add --card cards/m2/drift-card.json --model-id someone/m2-lora
$ keel ledger list --ledger ledger.jsonl
$ keel ledger recall --model-id someone/m2-lora --reason "24 of 32 harmful compliance"
```

## How the loop uses it

1. `keel watch` writes a queue of derivatives ranked by behavioural risk.
2. The scan step writes a card per candidate.
3. `keel ledger add` turns the card into a state.
4. The platform reads the ledger to decide whether the badge shows, changes, or is
   removed.
5. A human recall overrides everything until a human clears it.

## Why this is the right layer for a platform

A badge is a promise made once and read forever. The ledger is the mechanism that keeps
the promise current: it is append-only, so history is auditable; each entry carries the
card fingerprint, so a state can be traced to the exact measurement that produced it;
and the sticky recall means automation cannot quietly restore a label.

## What is still missing

- **Webhooks on transition.** The ledger is a file today; a platform needs a push event
  when a state changes.
- **A signed entry.** The fingerprint is tamper-evident, not tamper-proof.
- **Bulk expiry.** A card older than N days should return to `pending`, because the model
  may have changed even if the file did not.
