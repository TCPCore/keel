# Threat model

## What "external misalignment" means here

A third party modifies an open checkpoint and ships it. The modification is not a
prompt injection and does not pass through an API filter. The routes are:

| route | example | detectable by Keel |
|---|---|---|
| SFT / LoRA | insecure-code fine-tune causing broad drift | yes, both channels |
| preference training | narrowing refusal to a target domain | yes, both channels |
| direction ablation | removing a refusal direction | yes, white-box |
| merge / soup | a merge that dilutes safety training | yes, both channels |
| quantisation | 4-bit conversion damaging calibration | should be **green** — control |
| backdoor / trigger | behaviour that appears only on a trigger | partly; white-box probes help |
| system-prompt persona | a hosted endpoint steered by its prompt | yes, black-box (M5) |

## Who the tool is for

The developer who just downloaded a fine-tune and has no way to answer "is this
still safe?" except by red-teaming it for a week. Not the end user, and not a
model provider with a full eval stack.

## What Keel does not defend against

- **Coherent misalignment.** Probes detect conflict between what a model does and
  what it believes it is doing. A model that believes its harmful behaviour is
  virtuous produces no conflict signal. This is a documented blind spot, not an
  oversight.
- **A determined adversary who reimplements the panel.** Panels are public and
  therefore overfittable.
- **Anything at inference time.** Keel inspects checkpoints, not traffic.

## Dual use

A ranked list of safety units is also a list of units to remove. We accept this
because removal is already public and because defence needs the same list. The
lines we hold:

1. No misaligned weights in the repository, ever.
2. No harmful prompt corpus in the repository.
3. The organisms are recipes, not artefacts.
4. The card states its blind spots.

## Honest framing for the submission

"We built a smoke detector, and we can tell you which wires it does not see." A
safety tool that overstates its coverage is worse than no tool, because it
transfers risk to people who trust the number.
