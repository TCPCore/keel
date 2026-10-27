# Contributors

Keel is built by one human and several agents, and the split is deliberate: agents
write and critique at speed, a human decides and signs. This file records who did
what, so a reviewer can trace any claim, diff, or decision to its source.

## Participants

| name | kind | role | areas |
|---|---|---|---|
| **Tom** | human | Owner | product direction, provider and credit decisions, feedback, final sign-off. Name as configured in git; confirm the legal name before submission. |
| **Architect** — DeepSeek Harness (`deepseek-flash`) | agent | Architect and reviewer | design, measurement design, task briefs, code review and correction, git history, audit records |
| **Muse** — Muse Code 1.4.13 (`muse-spark-1.3`) | agent | Implementer | feature code generated from `muse/` briefs; first delivery was the white-box core (task 01) |
| **Reviewer** — external model, id not recorded | agent | Adversarial reviewer | the design critiques that forced the GPU question, the verb split, the cost correction, the M2 gate, and the demo-replay disclosure |

## Provenance by area

| area | authored by | reviewed by | where it lives |
|---|---|---|---|
| Hackathon rules and compliance | Architect | Owner | `DESIGN.md` §1 |
| Product framing and naming | Owner | Architect, Reviewer | `DESIGN.md` §14, `README.md` |
| Measurement: drift vector, statistics | Architect | Reviewer | `src/keel/stats.py`, `src/keel/drift.py`, `docs/METHOD.md` |
| Attribution method and controls | Architect | Reviewer | `src/keel/attribution.py`, `docs/METHOD.md` |
| White-box core: adapter, capture, intervention | Muse | Architect — three corrections | `src/keel/models.py`, `hooks.py`, `steer.py` |
| Panel and probe schema | Architect | — | `src/keel/panel.py`, `src/keel/data/` |
| Provider and compute plan | Architect | Reviewer, Owner | `docs/COMPUTE.md` |
| Repository policy and dual-use stance | Architect | Owner | `docs/REPO_POLICY.md`, `SECURITY.md` |
| Muse Code integration | Architect | Owner — supplied the credential | `scripts/muse_run.sh`, `muse/README.md` |
| Audit | Architect | Owner — pending | `audit/` |

## How attribution is recorded

- **`Co-authored-by: Muse Code`** on any commit that contains generated code.
- **`Audited-by:`** trailer on every commit; the pre-push hook refuses commits
  without one. See `scripts/audit_gate.py`.
- **`audit/<task>.md`** records the brief, the Muse session id, what was checked,
  and every correction applied to the generated work.
- **Muse session ids** are in the audit records, so a generated diff can be traced
  to a transcript under `.tools/runs/`.

Attribution is checked, not asserted: the trailers are enforceable, and the audit
records name the specific defects that were corrected.

## Authorship and licence

Agents cannot hold copyright or accept a licence. **The human owner is the author
of record** and the person who accepts the model licences, the event terms, and the
Apache-2.0 grant in `LICENSE`. Agents are credited for provenance and review; they
are not rights holders, and `CITATION.cff` lists the project rather than naming
them as authors.

## Acknowledgements

Keel was distilled from prior work, and the debt is specific:

- **[neuron-explorer](https://github.com/lyramakesmusic/neuron-explorer)** — the
  steering-first neuron explorer for Qwen3.5-4B. The sweep, the steer lens, the
  3D map, and the discipline of comparing every unit against random-direction
  controls come from it. Its `research_log.md` is the source of the dose
  calibration and the "did the output change is not a signal" warning.
- **[SafeNeuron](https://ar5iv.labs.arxiv.org/html/2602.12158)** — safety is
  concentrated in identifiable units, and can be made redundant.
- **[Refusal in Language Models Is Mediated by a Single Direction](https://proceedings.neurips.cc/paper_files/paper/2024/hash/f545448535dfde4f9786555403ab7c49-Abstract-Conference.html)** — one direction, one intervention, a large behavioural change.
- **[What Shapes Emergent Misalignment?](https://browse-export.arxiv.org/abs/2606.20814)** — pre-finetune activations predict post-finetune alignment.
- **[Why Safety Probes Catch Liars But Miss Fanatics](https://ar5iv.labs.arxiv.org/html/2603.25861)** — the blind spot this project prints instead of hiding.
- **[Meta Model API cookbook](https://github.com/meta-models/meta-model-cookbook)** — the API surface the black-box channel uses.

## Updating this file

Add a participant row when someone joins and a provenance row when an area changes
hands. Do not credit an agent without a session id or a commit range; "an AI helped"
is not provenance. If a contribution is corrected, record the correction rather than
rewriting the credit.
