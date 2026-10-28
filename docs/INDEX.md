# Docs index

Start with **STATUS.md**: what exists, what is proven, what is missing.

| doc | purpose |
|---|---|
| [STATUS.md](STATUS.md) | the current state of the product, evidence, and gaps |
| [METHOD.md](METHOD.md) | the drift math, panels, validity gates |
| [RESULTS.md](RESULTS.md) | every measurement, with caveats and failed runs |
| [HARMFUL-MATRIX.md](HARMFUL-MATRIX.md) | per-request compliance across checkpoints, no harmful text |
| [REPLAY_PROTOCOL.md](REPLAY_PROTOCOL.md) | the pre-registered tolerance for the replay test |
| [SUBMISSION.md](SUBMISSION.md) | deadline, rubric, required artifacts, ownership |
| [DEPLOY.md](DEPLOY.md) | three ways to deploy: CI gate, service, harness seam |
| [INTEGRATION.md](INTEGRATION.md) | Meta-internal and Hugging Face integration flows |
| [LIFECYCLE.md](LIFECYCLE.md) | label states: pending, verified, review, recalled |
| [AGENT.md](AGENT.md) | the watch, triage, scan, alert loop and the agent tool |
| [COMPUTE.md](COMPUTE.md) | providers, costs, and why attribution is not on Baseten |
| [TRAINING.md](TRAINING.md) | the LoRA environment and the free-GPU path |
| [THREAT_MODEL.md](THREAT_MODEL.md) | what the tool assumes an attacker can do |
| [REPO_POLICY.md](REPO_POLICY.md) | licensing and what is never committed |

## One-line summary

Keel is a checkpoint validity harness: it measures drift between a derivative and its
base, refuses to certify a measurement it cannot trust, records the label state, and
proves each card by fingerprint.
