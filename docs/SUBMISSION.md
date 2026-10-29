# Submission checklist

## Where it plugs into Meta Enterprise

The commercial version of the gap is an enterprise sale. A regulated buyer inherits a
derivative and cannot verify it; Keel turns that into an artifact the buyer can check. Four
insertion points, in order of integration cost:

1. **A provenance badge in the model API console.** A customer fine-tunes an open
   checkpoint, points the console at it, and the model carries a fingerprint and a policy
   decision next to the endpoint they already pay for.
2. **An enterprise contract clause.** "This deployment is a verified derivative, attested
   against its base on this date" is a renewal and win-rate lever for regulated buyers, not
   a new SKU.
3. **A CI gate in the customer pipeline.** `keel policy` already exits allow, review or
   block, so a release pipeline can gate on a checkpoint the same way it gates on tests.
4. **An audit export.** The card is one JSON with the fingerprint and the decision, which
   is the form auditors ask for.

The strategic argument for buying rather than building is independence: a vendor's own
attestation is a claim, and a third-party fingerprint is evidence. The counter-argument is
that Meta could open-source it, as it did with the guard models, which would make it a
standard rather than a product.

For a seller, the sentence is: **Meta's enterprise customers inherit derivatives they
cannot verify; Keel gives them a badge, a gate and an audit export, using the same
measurements that caught the 0.81 ablation.**

## The gap this fills

Meta checks the base model before release, and its runtime guards check the conversation
after deployment. Nothing checks the derivative artifact in between. Open weights make that
hole structural: a derivative can remove refusal behaviour, and the only record of what it
became is a licence label its author typed.

Keel is the checkpoint layer of that stack. One command produces a card that states what
moved against the base, whether the measurement was valid, how often the model complies
with harmful requests, and a fingerprint that proves the card was not edited.

The evidence that this is a class problem, not a Glimmer quirk: the same method reproduces
on Meta Glimmer 30B, Qwen 2.5 7B and Mistral 7B, including two derivatives we did not
build.

Decoded from the event page and the embedded Hackathon Terms & Conditions
(`cerebralvalley.ai/e/meta-ai-developer-hackathon/details`), 26 Oct 2026.

## Deadline

| milestone | time |
|---|---|
| Project submissions due | **4 Nov 2026, 9:00 PM ET / 6:00 PM PT** |
| Judging | 4–8 Nov |
| Winners announced | 9 Nov |

## Track and theme

- **Track:** startup. One track only; a project cannot be entered in both.
- **Representative:** one individual submits on behalf of the team and is named in
  the submission. All team members must be identified.
- **Theme:** whichever was declared on the application (Build for Your World, or
  Push the Frontier). The README's framing should match it.

## Judging rubric — confirmed

| criterion | weight | what they actually look for |
|---|---|---|
| Impact | 30% | real-world potential, who benefits, could it become something people use, fit to a problem statement |
| Use of Meta AI Tooling | 25% | creativity, **beyond a basic integration**, unexpected capabilities |
| Technical Depth & Execution | 20% | sound engineering, refinement, craft |
| Demo | 25% | working demo, **holds up live**, and the **quality of the demo video** |

The tooling criterion is the one this project can score on rather than merely
satisfy: the tool is built with Muse Code, run against Muse Spark through the Meta
Model API and Baseten, and aimed at Meta open weights. That is not a wrapper.

## Required artifacts

- [x] Public repository, licensed, with a README that states what works and what does not
- [x] **Demo video** — built and hosted at `/demo.mp4`; source in `video/keel-demo.mp4`.
  Ten annotated scenes, 1:55, narration and burned captions.
- [x] A working demo that holds up live: https://tomscot-keel.hf.space
- [x] Submission text: written locally by cptlight and submitted directly, not in this repo.
- [ ] Representative named; all team members identified (owner action)
- [ ] Theme and track stated (owner action)
- [ ] Official Rules accepted

Current state of each item is tracked in [STATUS.md](STATUS.md).

## Ownership and IP — read this before pushing

The terms require the Participant to represent and warrant that the Submission:

> (a) is their (or their applicable team's or organization's) original work product;
> (b) is **solely owned by the Participant**, with **no other person or entity
> having any right or interest in it**; and (c) does not violate the intellectual
> property or other proprietary rights of any other person or entity.

And, on assistance:

> Participants may contract with a third party for technical assistance, provided
> the Submission components remain the Participant's own work and the Participant
> owns all rights to them. Participants may also include open source software,
> provided applicable open source licenses are followed.

The Participant retains ownership and grants the Organizers a perpetual,
irrevocable, worldwide, royalty-free, non-exclusive licence to use, reproduce,
adapt, publish, and create derivative works for any purpose, including marketing.

### What that means here

Agent-generated code is permitted as technical assistance, and this repository
already documents the boundary: `CONTRIBUTORS.md` names cptlight as author of
record and the agents as non-rights-holders, and the humans directed and reviewed
every generated diff.

Two things still need doing:

1. **Check the output-ownership terms of the tools used** — Meta Model API, Muse
   Code, Baseten. If any of them retains a licence over outputs, say so in the
   submission rather than representing sole ownership without qualification.
2. **Keep the review trail** — the `audit/` records and `Co-authored-by` trailers
   are evidence that the submission is directed human work, not an unexamined dump.

## What is still missing

| item | status |
|---|---|
| Public repo | local only; no remote, push blocked by the audit gate |
| Demo video | not started |
| Live demo | synthetic demo only |
| Submission text | not written |
| Official Rules accepted | pending |
| Team/Representative details | pending |
